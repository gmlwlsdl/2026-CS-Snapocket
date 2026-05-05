export type ApiNodeCategory = string;

export interface ApiNode {
  id: string;
  title: string;
  category: ApiNodeCategory;
  tags: string[];
  createdAt: string;
  connectionCount: number;
}

export interface ApiEdge {
  source: string;
  target: string;
  weight: number;
  edgeType: "parent_of" | "related_to" | "similar_to" | string;
}

export interface GraphSummaryData {
  node_count: number;
  document_count: number;
  documents_count?: number;
  tag_count: number;
  edge_count: number;
}

export interface GraphData {
  nodes: ApiNode[];
  edges: ApiEdge[];
}

export interface SearchNodeResult {
  id: string;
  title: string;
  category: string;
  highlight: string;
}
