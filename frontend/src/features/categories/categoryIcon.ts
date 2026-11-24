const side = 16
const encodedIcon = /^px:[A-Za-z0-9+/]{43}$/
const imageTypes = ['image/png', 'image/jpeg', 'image/webp']

export async function compactCategoryIcon(file: File) {
  if (!imageTypes.includes(file.type) || file.size > 2 * 1024 * 1024) {
    throw new Error('Choose a PNG, JPEG, or WebP image under 2 MB.')
  }

  const image = await createImageBitmap(file, { resizeWidth: side, resizeHeight: side, resizeQuality: 'high' })
  try {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = side
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Image processing is unavailable in this browser.')
    context.drawImage(image, 0, 0)
    const { data } = context.getImageData(0, 0, side, side)
    const alpha = data.some((value, index) => index % 4 === 3 && value < 128)
    const bytes = new Uint8Array(side * side / 8)
    for (let pixel = 0; pixel < side * side; pixel++) {
      const index = pixel * 4
      const brightness = data[index] * .2126 + data[index + 1] * .7152 + data[index + 2] * .0722
      if (alpha ? data[index + 3] >= 128 : brightness < 160) {
        bytes[pixel >> 3] |= 128 >> (pixel % 8)
      }
    }
    if (!bytes.some(value => value !== 0)) throw new Error('Choose an image with a visible shape.')
    return 'px:' + btoa(String.fromCharCode(...bytes)).slice(0, -1)
  } finally {
    image.close()
  }
}

export function categoryIconPath(icon: string) {
  if (!encodedIcon.test(icon)) return null
  const bytes = atob(icon.slice(3) + '=')
  let path = ''
  for (let pixel = 0; pixel < side * side; pixel++) {
    if (bytes.charCodeAt(pixel >> 3) & (128 >> (pixel % 8))) {
      path += `M${pixel % side} ${Math.floor(pixel / side)}h1v1h-1z`
    }
  }
  return path
}
