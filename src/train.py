"""Selecciona checkpoint por F1 macro de validación; nunca consulta prueba."""
import argparse, copy, hashlib, json, random
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score
from src.common import ROOT, Leaves, build, read_rows

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=['cnn','mobilenet','resnet18'], default='mobilenet')
    p.add_argument('--epochs', type=int, default=10)
    p.add_argument('--batch-size', type=int, default=16)
    args = p.parse_args()
    if args.epochs < 1 or args.batch_size < 1: p.error('epochs y batch-size deben ser positivos')
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    rows = read_rows(); classes = sorted({r['label'] for r in rows})
    train = [r for r in rows if r['split']=='train']
    val = [r for r in rows if r['split']=='val']
    loaders = {k: DataLoader(Leaves(v,classes,k=='train'), batch_size=args.batch_size,
        shuffle=k=='train', num_workers=0) for k,v in [('train',train),('val',val)]}
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = build(args.model,len(classes),args.model!='cnn').to(device)
    counts = np.array([sum(r['label']==c for r in train) for c in classes])
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(len(train)/(len(classes)*counts),dtype=torch.float32,device=device))
    opt = torch.optim.Adam(filter(lambda p:p.requires_grad,model.parameters()),lr=0.001)
    best, state, history = -1, None, []
    for epoch in range(args.epochs):
        model.train()
        # Mantener BatchNorm del extractor congelado en modo evaluación.
        if args.model=='mobilenet': model.features.eval()
        elif args.model=='resnet18':
            model.eval(); model.fc.train()
        total = 0.0
        for x,y in loaders['train']:
            x,y = x.to(device),y.to(device)
            opt.zero_grad(); loss=criterion(model(x),y); loss.backward(); opt.step()
            total += loss.item()*len(y)
        model.eval(); truth,pred=[],[]
        with torch.no_grad():
            for x,y in loaders['val']:
                truth.extend(y.tolist()); pred.extend(model(x.to(device)).argmax(1).cpu().tolist())
        score = f1_score(truth,pred,labels=list(range(len(classes))),average='macro',zero_division=0)
        history.append({'epoch':epoch+1,'train_loss':total/len(train),'val_macro_f1':score})
        print(history[-1],flush=True)
        if score>best:
            best=score; state=copy.deepcopy({k:v.cpu() for k,v in model.state_dict().items()})
    (ROOT/'models').mkdir(exist_ok=True)
    torch.save({'state_dict':state,'classes':classes,'model':args.model,'val_macro_f1':best,
        'manifest_sha256':hashlib.sha256((ROOT/'data/processed/manifest.csv').read_bytes()).hexdigest(),
        'seed':42,'epochs':args.epochs},ROOT/f'models/{args.model}.pt')
    (ROOT/f'reports/{args.model}_history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
    print(f'Modelo guardado. Dispositivo: {device}. F1 validación: {best:.4f}')

if __name__=='__main__': main()
