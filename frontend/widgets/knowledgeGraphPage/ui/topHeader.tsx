"use client";

import type { CategoryFilter } from "../knowledgeGraph.type";
import type { GraphSummaryData } from "@/entities/graph";
import { CATEGORY_FILTERS } from "../knowledgeGraph.constant";
import { ThemeToggle } from "@/shared/ui";
import { Chip, Group } from "@mantine/core";

interface TopHeaderProps {
  activeFilter: CategoryFilter;
  onFilterChange: (filter: CategoryFilter) => void;
  summaryData?: GraphSummaryData;
}

export function TopHeader({ activeFilter, onFilterChange, summaryData }: TopHeaderProps) {
  const documentCount = summaryData?.document_count ?? summaryData?.documents_count ?? 0;

  return (
    <header
      className="fixed left-0 right-0 top-0 z-20 flex h-16 items-center px-6"
      style={{
        background: "var(--th-header-bg)",
        backdropFilter: "blur(12px)",
        // borderBottom: "1px solid var(--th-separator)",
      }}
    >
      <div className="flex w-[256px] shrink-0 items-center gap-3">
        <div className="flex flex-col overflow-hidden whitespace-nowrap">
          <span
            className="font-manrope text-xl font-bold leading-7"
            style={{
              background: 'linear-gradient(90deg, #97c2ec 0%, #ac89ff 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: '-0.4px',
            }}
          >
            Snapocket
          </span>
          <span
            className="font-inter text-[10px] font-bold tracking-[2px]"
            style={{ color: 'var(--th-text-faint)' }}
          >
            Intelligent Graph
          </span>
        </div>
      </div>

      {/* 카테고리 칩 */}
      <Chip.Group value={activeFilter} onChange={(v) => onFilterChange(v as CategoryFilter)}>
        <Group gap={6}>
          {CATEGORY_FILTERS.map(({ id, label }) => (
            <Chip
              key={id}
              value={id}
              size="xs"
              radius="xl"
              styles={{
                label: {
                  fontFamily: 'var(--font-manrope), Manrope, sans-serif',
                  fontSize: 12,
                  fontWeight: 500,
                  letterSpacing: -0.4,
                  paddingInline: 16,
                  height: 28,
                  background: activeFilter === id ? 'linear-gradient(135deg, #97c2ec 0%, #7daed8 100%)' : '',
                  color: activeFilter === id ? 'var(--th-chip-active-text)' : '',
                },
              }}
            >
              {label}
            </Chip>
          ))}
        </Group>
      </Chip.Group>

      <div className="ml-auto flex items-center gap-6">
        <div className="flex flex-col items-end">
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Nodes
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {summaryData?.node_count ?? 0}
          </span>
        </div>
        <div
          className="flex flex-col items-end pl-6"
          style={{ borderLeft: "1px solid var(--th-border)" }}
        >
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Docs
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {documentCount}
          </span>
        </div>
        <div
          className="flex flex-col items-end pl-6"
          style={{ borderLeft: "1px solid var(--th-border)" }}
        >
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Tags
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {summaryData?.tag_count ?? 0}
          </span>
        </div>
        <div
          className="flex flex-col items-end pl-6"
          style={{ borderLeft: "1px solid var(--th-border)" }}
        >
          <span
            className="text-[10px] uppercase tracking-[1px]"
            style={{ color: "var(--th-text-faint)" }}
          >
            Edges
          </span>
          <span className="text-[14px] font-bold" style={{ color: "var(--th-text)" }}>
            {summaryData?.edge_count ?? 0}
          </span>
        </div>

        <div className="pl-4" style={{ borderLeft: "1px solid var(--th-border)" }}>
          <ThemeToggle />
        </div>
      </div>

      <style>{`
        @media (max-width: 768px) {
          header {
            left: 0 !important;
            flex-direction: column !important;
            height: auto !important;
            padding: 12px !important;
            gap: 8px !important;
            align-items: stretch !important;
          }
          header > div:first-child {
            display: flex !important;
            justify-content: space-between !important;
            width: 100% !important;
          }
          header nav {
            overflow-x: auto !important;
            white-space: nowrap !important;
            padding-bottom: 4px !important;
            justify-content: flex-start !important;
            width: 100% !important;
            scrollbar-width: none;
          }
          header nav::-webkit-scrollbar {
            display: none;
          }
          header > div:last-child {
            display: none !important;
          }
        }
      `}</style>
    </header>
  );
}
