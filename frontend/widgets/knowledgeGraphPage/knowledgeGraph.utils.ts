import type { NodeCategory } from "./knowledgeGraph.type";

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
