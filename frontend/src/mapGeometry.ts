/** Image-space geometry. Units are normalized unless a function says pixels. */
export type MapPoint = { x: number; y: number }
export const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value))

export function pointAlongRoute(route: MapPoint[], progress: number): MapPoint | null {
  if (!route.length) return null
  if (route.length === 1) return { ...route[0]! }
  if (progress <= 0) return { ...route[0]! }
  if (progress >= 100) return { ...route[route.length - 1]! }
  const distances = route.slice(1).map((point, i) => Math.hypot(point.x - route[i]!.x, point.y - route[i]!.y))
  const total = distances.reduce((sum, distance) => sum + distance, 0)
  if (!total) return { ...route[0]! }
  let remaining = total * clamp(progress, 0, 100) / 100
  for (let i = 0; i < distances.length; i++) {
    const distance = distances[i]!
    if (remaining <= distance && distance > 0) {
      const ratio = remaining / distance
      const from = route[i]!, to = route[i + 1]!
      return { x: from.x + (to.x - from.x) * ratio, y: from.y + (to.y - from.y) * ratio }
    }
    remaining -= distance
  }
  return { ...route[route.length - 1]! }
}

/** Keep the camera within the image, including when viewport has letterboxing. */
export function cameraBounds(center: MapPoint, zoom: number, width: number, height: number): MapPoint {
  const halfWidth = width / zoom / 2, halfHeight = height / zoom / 2
  return { x: clamp(center.x, halfWidth, width - halfWidth), y: clamp(center.y, halfHeight, height - halfHeight) }
}
