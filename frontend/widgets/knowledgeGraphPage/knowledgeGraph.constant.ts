import type { CategoryFilter } from "./knowledgeGraph.type";

export const CANVAS_WIDTH = 1200;
export const CANVAS_HEIGHT = 1024;


export const CATEGORY_FILTERS: { id: CategoryFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "lecture", label: "Lecture" },
  { id: "assignment", label: "Assignment" },
  { id: "notice", label: "Notice" },
  { id: "receipt", label: "Receipt" },
  { id: "memo", label: "Memo" },
];

export const NODE_DOT_SIZE: Record<string, number> = {
  root: 11,
  primary: 7,
  secondary: 4,
};

export const NODE_COLOR: Record<string, string> = {
  root: "#f1f7ff",
  assignment: "#e05a67",
  lecture: "#d7a256",
  notice: "#8fd26a",
  receipt: "#7d8791",
  memo: "#74c3d5",
  exam: "#f0c35a",
  class: "#d7a256",
  summary: "#9ac7ff",
  misc: "#9aa4af",
};

export const NODE_DOT_OPACITY: Record<string, number> = {
  root: 1,
  primary: 0.8,
  secondary: 0.6,
};
