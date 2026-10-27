export type Species = "dog" | "cat" | "human" | "all";
export interface SearchRequest {
  gene: string;
  species: Species;
  limit: number;
  year_from: number | null;
  year_to: number | null;
  cancer_keyword: string | null;
}
export interface Article {
  pmid: string;
  doi: string | null;
  title: string | null;
  abstract: string | null;
  abstract_available: boolean;
  authors: string[];
  publication_year: number | null;
  journal: string | null;
  source_url: string;
  ncbi_retrieved_at: string;
  mesh_terms: string[];
  publication_types: string[];
  species_status: "unverified";
  species_evidence_strength: "low";
  species_evidence_notes: string[];
}
export interface SearchResponse {
  articles: Article[];
  total_count: number;
  returned_count: number;
  searched_at: string;
  query_string: string;
  query_translation: string;
  esearch_retrieved_at: string;
  is_partial: boolean;
  failed_pmids: string[];
  failed_count: number;
  failures: Record<string, string>;
  warnings: Record<string, string[]>;
  from_cache: false;
  message: string | null;
}
