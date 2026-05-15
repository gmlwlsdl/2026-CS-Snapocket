export type NodeCategory = "assignment" | "exam" | "class" | "summary" | "misc" | "root" | "lecture" | "notice" | "receipt" | "memo";

export type NodeSize = "root" | "primary" | "secondary";
export type GraphEdgeType = "parent_of" | "related_to" | "similar_to";

export interface GraphNode {
  id: string;
  label: string;
  x: number;
  y: number;
  fx?: number;
  fy?: number;
  category: NodeCategory;
  size: NodeSize;
  connectionCount?: number;
  depth?: number;
  clusterId?: string;
}

export interface GraphEdge {
  from: string;
  to: string;
  weight: number;
  type: GraphEdgeType;
}

export type CategoryFilter = "all" | "lecture" | "assignment" | "notice" | "receipt" | "memo";
