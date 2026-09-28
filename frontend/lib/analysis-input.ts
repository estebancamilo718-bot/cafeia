const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png"]);
const ALLOWED_EXTENSIONS = /\.(jpe?g|png)$/i;

type FileMetadata = Pick<File, "name" | "size" | "type">;

export function validateSelectedImage(file: FileMetadata): string | null {
  if (!ALLOWED_TYPES.has(file.type) || !ALLOWED_EXTENSIONS.test(file.name)) {
    return "Selecciona una fotografía JPG o PNG válida.";
  }
  if (file.size > MAX_FILE_SIZE) {
    return "La fotografía no puede superar 10 MB.";
  }
  return null;
}

export function analysisFailureMessage(reason: unknown): string {
  if (reason instanceof TypeError) {
    return "No se pudo conectar con CaféIA. Comprueba que el backend esté encendido.";
  }
  if (reason instanceof Error) return reason.message;
  return "Ocurrió un error inesperado.";
}
