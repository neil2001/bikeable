/** Lucide `X` as a DOM SVG for MapLibre marker chrome. */
export function createLucideX(size = 12): SVGSVGElement {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.style.width = `${size}px`;
  svg.style.height = `${size}px`;
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2.5");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");

  const a = document.createElementNS("http://www.w3.org/2000/svg", "path");
  a.setAttribute("d", "M18 6 6 18");
  const b = document.createElementNS("http://www.w3.org/2000/svg", "path");
  b.setAttribute("d", "m6 6 12 12");
  svg.append(a, b);
  return svg;
}
