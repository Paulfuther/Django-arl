window.pica_resize = async function(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = function (e) {
      const img = new Image();
      img.src = e.target.result;

      img.onload = async function () {
        try {
          const canvas = document.createElement("canvas");
          const maxWidth = 1200;
          const scale = Math.min(maxWidth / img.width, 1);
          canvas.width = img.width * scale;
          canvas.height = img.height * scale;

          const resizer = pica();
          await resizer.resize(img, canvas);
          const blob = await resizer.toBlob(canvas, file.type, 0.9);

          const resizedFile = new File([blob], file.name, { type: file.type });
          resolve(resizedFile);
        } catch (err) {
          reject(err);
        }
      };

      img.onerror = () => reject("❌ Failed to load image.");
    };

    reader.onerror = () => reject("❌ Failed to read file.");
    reader.readAsDataURL(file);
  });
}