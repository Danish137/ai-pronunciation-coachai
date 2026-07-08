export const MIN_SECONDS = 30;
export const MAX_SECONDS = 45;

export async function getAudioDurationSeconds(file: Blob) {
  return new Promise<number>((resolve, reject) => {
    const audio = document.createElement("audio");
    const url = URL.createObjectURL(file);

    audio.preload = "metadata";
    audio.src = url;
    audio.onloadedmetadata = () => {
      const duration = audio.duration;
      URL.revokeObjectURL(url);
      resolve(duration);
    };
    audio.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Unable to read the selected audio file."));
    };
  });
}

export async function validateAudioDuration(file: Blob) {
  const duration = await getAudioDurationSeconds(file);
  if (duration < MIN_SECONDS || duration > MAX_SECONDS) {
    throw new Error(`Audio must be between ${MIN_SECONDS} and ${MAX_SECONDS} seconds.`);
  }
  return duration;
}
