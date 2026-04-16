import type { ApiNode, ApiNodeCategory } from "@/entities/graph";
import type { GraphNode, NodeCategory, NodeSize } from "./knowledgeGraph.type";
import { CANVAS_WIDTH, CANVAS_HEIGHT } from "./knowledgeGraph.constant";

export const CATEGORY_TO_NODE_CATEGORY: Record<string, NodeCategory> = {
  // Singular (Backend)
  lecture: "lecture",
  assignment: "assignment",
  notice: "notice",
  receipt: "receipt",
  memo: "memo",
  // Legacy/Plural
  assignments: "assignment",
  exams: "exam",
  class_materials: "class",
  summaries: "summary",
  receipts: "receipt",
  notices: "notice",
};

// 각 카테고리의 기준 각도 (degree)
const CATEGORY_BASE_ANGLE: Record<string, number> = {
  lecture: 0,
  assignment: 60,
  notice: 120,
  receipt: 180,
  memo: 240,
  // Legacy
  assignments: 60,
  exams: 0,
  class_materials: -60,
  summaries: 120,
  receipts: 180,
  notices: 240,
};

export function computeNodePositions(apiNodes: ApiNode[]): GraphNode[] {
  const cx = CANVAS_WIDTH / 2;
  const cy = CANVAS_HEIGHT / 2;

  const categoryGroups = new Map<string, ApiNode[]>();
  for (const node of apiNodes) {
    if (!categoryGroups.has(node.category)) {
      categoryGroups.set(node.category, []);
    }
    categoryGroups.get(node.category)!.push(node);
  }

  const result: GraphNode[] = [];

  for (const [category, nodes] of categoryGroups) {
    const baseRad = ((CATEGORY_BASE_ANGLE[category] ?? 0) * Math.PI) / 180;

    nodes.forEach((node, i) => {
      const radius = 220 + Math.floor(i / 3) * 90;
      const angleOffset = ((i % 3) - 1) * (Math.PI / 9);
      const angle = baseRad + angleOffset;
      const x = cx + radius * Math.cos(angle);
      const y = cy + radius * Math.sin(angle);
      const size: NodeSize = i === 0 ? "primary" : "secondary";

      result.push({
        id: node.id,
        label: node.title,
        x: Math.round(Math.max(60, Math.min(CANVAS_WIDTH - 60, x))),
        y: Math.round(Math.max(60, Math.min(CANVAS_HEIGHT - 60, y))),
        category: CATEGORY_TO_NODE_CATEGORY[category] ?? "misc",
        size,
      });
    });
  }

  return result;
}
