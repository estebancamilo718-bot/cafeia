from pathlib import Path
import torch
import streamlit as st
from PIL import Image, ImageOps, UnidentifiedImageError
from src.common import ROOT, load_checkpoint, transform

st.set_page_config(page_title='Agente de hojas de café',page_icon='🌿')
st.title('🌿 Agente de clasificación de hojas de café')
st.write('Prototipo académico: sana, roya o ácaro rojo. Carga una fotografía de una hoja de café.')
paths=sorted((ROOT/'models').glob('*.pt'))
if not paths:
    st.info('Todavía no hay un modelo entrenado. Sigue LEEME.md para preparar datos y entrenar.')
    st.stop()
selected=st.selectbox('Modelo entrenado',paths,format_func=lambda p:p.stem)
@st.cache_resource
def get_model(path, modified):
    return load_checkpoint(path)
model,ck=get_model(str(selected),selected.stat().st_mtime_ns)
file=st.file_uploader('Fotografía',type=['jpg','jpeg','png'])
if file:
    try:
        im=ImageOps.exif_transpose(Image.open(file)).convert('RGB')
        st.image(im,width=350)
        with torch.no_grad(): probs=torch.softmax(model(transform()(im).unsqueeze(0)),dim=1)[0]
        idx=int(probs.argmax()); score=float(probs[idx])
        names={'coffee___healthy':'Hoja sana','coffee___rust':'Roya','coffee___red_spider_mite':'Ácaro rojo'}
        st.subheader(names.get(ck['classes'][idx],ck['classes'][idx]))
        st.write(f'Puntuación del modelo: {score:.1%}')
        st.caption('Esta puntuación no es una probabilidad calibrada de acierto. El sistema no detecta automáticamente imágenes ajenas al café.')
        if score<0.70: st.warning('Predicción incierta: solicitar otra fotografía o revisión humana. Umbral provisional pendiente de validar.')
        else: st.info('Clasificación orientativa. Si se observan daños, solicitar revisión de una persona experta.')
        st.bar_chart({names.get(c,c):float(probs[i]) for i,c in enumerate(ck['classes'])})
    except (UnidentifiedImageError, OSError): st.error('No se pudo leer la imagen. Prueba otro archivo.')
