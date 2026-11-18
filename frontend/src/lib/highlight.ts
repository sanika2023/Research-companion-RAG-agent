export type PageSize = { width: number; height: number }; // PDF points

export type BoxStyle = { left: string; top: string; width: string; height: string };

/**
 * Citation bounding boxes ([x0, y0, x1, y1] in PDF points, origin top-left, as PyMuPDF
 * reports them) as percentages of the page, so highlights stay aligned at any zoom.
 */
export function highlightBoxes(bbox: number[][], page: PageSize): BoxStyle[] {
  const percent = (value: number, total: number) => `${(value / total) * 100}%`;
  return bbox.flatMap((box) => {
    const [x0, y0, x1, y1] = box;
    if (x0 === undefined || y0 === undefined || x1 === undefined || y1 === undefined) return [];
    return [
      {
        left: percent(x0, page.width),
        top: percent(y0, page.height),
        width: percent(x1 - x0, page.width),
        height: percent(y1 - y0, page.height),
      },
    ];
  });
}
