import { callHeatmapAnchors } from "./map";
async function logHeatmapAnchors(): Promise<void> {
  try {
    const anchors = await callHeatmapAnchors();

    console.log(JSON.stringify(anchors.Houston[0]['2026-07-05']));
  } catch (error) {
    console.error("Failed to fetch heatmap anchors:", error);
  }
}

logHeatmapAnchors();