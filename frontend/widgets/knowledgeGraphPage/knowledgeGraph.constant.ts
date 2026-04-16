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
  root: 8,
  primary: 5,
  secondary: 3,
};

export const NODE_COLOR: Record<string, string> = {
  root: "#81ecff",
  assignment: "#81ecff",
  lecture: "#81ecff",
  notice: "#81ecff",
  receipt: "#81ecff",
  memo: "#81ecff",
  exam: "#81ecff",
  class: "#81ecff",
  summary: "#81ecff",
  misc: "#81ecff",
};

export const NODE_DOT_OPACITY: Record<string, number> = {
  root: 1,
  primary: 0.8,
  secondary: 0.6,
};
