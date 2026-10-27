import type { Article } from "./types";

// Shows where the searched spelling occurs in fields PubMed's [tiab] covers.
// It reports text positions only; it never infers mutations, findings or species.
export interface TermMatches {
  inTitle: boolean;
  abstractSentences: string[];
  abstractCount: number;
  keywords: string[];
}

const escape = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// Whole-token, case-insensitive match: "BRAF" matches "BRAF-mutant" but not "BRAFV595E".
// PubMed also indexes hyphenated spellings without the hyphen, so "B-Raf" matches "BRAF".
const hyphenTolerant = (word: string) =>
  [...word.replace(/-/g, "")].map(escape).join("-?");
export function termPattern(term: string): RegExp | null {
  const words = term.trim().split(/\s+/).filter(Boolean).map(hyphenTolerant);
  if (!words.length) return null;
  return new RegExp(`(?<![\\p{L}\\p{N}])${words.join("\\s+")}(?![\\p{L}\\p{N}])`, "giu");
}

// Sentences are verbatim slices of the abstract; structured sections stay separate.
export function splitSentences(text: string): string[] {
  return text
    .split(/\n+|(?<=[.!?])\s+(?=[\p{Lu}\p{N}(["])/u)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function count(text: string, pattern: RegExp) {
  return text.match(pattern)?.length ?? 0;
}

export function findTermMatches(article: Article, term: string): TermMatches | null {
  const pattern = termPattern(term);
  if (!pattern) return null;
  const abstract = article.abstract_available && article.abstract ? article.abstract : "";
  return {
    inTitle: count(article.title ?? "", pattern) > 0,
    abstractSentences: splitSentences(abstract).filter((s) => count(s, pattern) > 0),
    abstractCount: count(abstract, pattern),
    keywords: article.keywords.filter((k) => count(k, pattern) > 0),
  };
}
