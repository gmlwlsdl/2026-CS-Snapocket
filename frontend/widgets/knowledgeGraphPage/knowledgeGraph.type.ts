export type NodeCategory = "assignment" | "exam" | "class" | "summary" | "misc" | "root" | "lecture" | "notice" | "receipt" | "memo";

export type NodeSize = "root" | "primary" | "secondary";

export interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  category: NodeCategory;
  size: NodeSize;
}

export interface GraphEdge {
  from: string;
  to: string;
  weight: number;
}

export type CategoryFilter = "all" | "lecture" | "assignment" | "notice" | "receipt" | "memo";
