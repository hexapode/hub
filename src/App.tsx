/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Check,
  ChevronRight,
  Copy,
  ExternalLink,
  FileCode2,
  Play,
  Search,
  Sun,
  Moon,
  Terminal,
  AlertTriangle,
} from 'lucide-react';
import logoUrl from './assets/images/superautoresearch_logo_1792954930815.jpg';

interface MetricSpec {
  name: string;
  unit?: string;
  direction: 'min' | 'max';
  scale?: 'linear' | 'log';
  display?: string;
}

interface RecordEntry {
  id: string;
  value: number;
  evidence: 'verified' | 'claimed';
  author: string;
  agent?: string;
  model?: string;
  date: string;
  pr?: number;
  commit?: string;
  url?: string;
}

interface TrackItem {
  id: string;
  title: string;
  notes?: string;
}

interface GlobalRow {
  slug: string;
  title: string;
  summary?: string;
  kind: 'native' | 'external';
  repo: string;
  repo_url: string;
  tags: string[];
  verifier_type: 'script' | 'lean' | 'manual' | 'custom';
  metric: MetricSpec;
  baseline: { value: number; label: string; source?: string };
  first_record: RecordEntry | null;
  current_best: RecordEntry | null;
  best_claim: RecordEntry | null;
  records_count: number;
  contributors: number;
  attempts: number;
  last_improved: string | null;
  status: 'ok' | 'statement-changed' | 'unreachable' | 'invalid';
}

interface IndexChallenge {
  slug: string;
  kind: 'native' | 'external';
  repo: string;
  owners: string[];
  tags: string[];
  title: string;
  summary: string;
  metric: MetricSpec;
  baseline: { value: number; label: string };
  verifier: { type: string; runner?: string; timeout?: string };
  tracks: TrackItem[];
  open_tracks: TrackItem[];
  active_claims: any[];
  repo_url: string;
  agents_md_url: string;
  attempt_log_url: string;
  status: string;
}

declare global {
  interface Window {
    katex?: {
      renderToString: (tex: string, opts?: { throwOnError?: boolean }) => string;
    };
  }
}

function formatEvidenceLabel(verifierType: string, evidence?: string): string {
  if (evidence === 'claimed') return 'Claimed';
  if (verifierType === 'lean') return 'Lean verified';
  if (verifierType === 'manual') return 'Human verified';
  return 'Verified';
}

function formatNumericValue(value: number): string {
  if (!Number.isFinite(value)) return String(value);
  if (Math.abs(value) > 0 && (Math.abs(value) < 1e-4 || Math.abs(value) >= 1e6)) {
    return value.toExponential(4);
  }
  return String(Number(value.toPrecision(6)));
}

function MetricDisplay({ value, metric }: { value: number | null | undefined; metric: MetricSpec }) {
  if (value === null || value === undefined) return <span>—</span>;
  const formattedVal = formatNumericValue(value);
  const display = metric?.display || '{value}';
  const unit = metric?.unit || '';
  let raw = display.replace('{value}', formattedVal);
  if (!metric?.display && unit) {
    raw = `${formattedVal} ${unit}`;
  }
  const needsKatex = raw.includes('^') || raw.includes('_') || raw.includes('\\');
  if (needsKatex && typeof window !== 'undefined' && window.katex) {
    try {
      const html = window.katex.renderToString(raw, { throwOnError: false });
      return <span className="font-mono tabular-nums" dangerouslySetInnerHTML={{ __html: html }} />;
    } catch {
      // Fallback to plain text
    }
  }
  return <span className="font-mono tabular-nums">{raw}</span>;
}

function RecordStepChart({
  baselineValue,
  records,
  claims,
  metric,
  dark,
}: {
  baselineValue: number;
  records: RecordEntry[];
  claims: RecordEntry[];
  metric: MetricSpec;
  dark: boolean;
}) {
  const points = useMemo(() => {
    const basePt = { label: 'Baseline', value: baselineValue, author: 'baseline', isBaseline: true };
    const recPts = records.map((r) => ({
      label: (r.date || '').slice(0, 10),
      value: r.value,
      author: r.author,
      isBaseline: false,
    }));
    return [basePt, ...recPts];
  }, [baselineValue, records]);

  const allValues = [
    ...points.map((p) => p.value),
    ...claims.map((c) => c.value),
  ];
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const span = Math.max(maxVal - minVal, 1e-6);

  const width = 640;
  const height = 230;
  const padL = 56;
  const padR = 28;
  const padT = 22;
  const padB = 38;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const totalSlots = Math.max(points.length + claims.length, 2);
  const xForIdx = (idx: number) => padL + (idx / (totalSlots - 1)) * plotW;
  const yForVal = (v: number) => padT + ((maxVal - v) / span) * plotH;

  // Build step path for verified records
  const stepSegments: string[] = [];
  points.forEach((pt, idx) => {
    const x = xForIdx(idx);
    const y = yForVal(pt.value);
    if (idx === 0) {
      stepSegments.push(`M ${x} ${y}`);
    } else {
      const prevY = yForVal(points[idx - 1].value);
      stepSegments.push(`L ${x} ${prevY}`);
      stepSegments.push(`L ${x} ${y}`);
    }
  });

  const gridStroke = dark ? '#334155' : '#e2e8f0';
  const textFill = dark ? '#94a3b8' : '#64748b';
  const lineStroke = dark ? '#38bdf8' : '#0284c7';

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-56 overflow-visible">
      {[0, 0.5, 1].map((frac, i) => {
        const val = maxVal - frac * span;
        const y = padT + frac * plotH;
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={width - padR} y2={y} stroke={gridStroke} strokeDasharray="3 3" />
            <text
              x={padL - 8}
              y={y + 4}
              textAnchor="end"
              fontSize="11"
              fill={textFill}
              className="font-mono tabular-nums"
            >
              {Number(val.toPrecision(4))}
            </text>
          </g>
        );
      })}

      {stepSegments.length > 0 && (
        <path d={stepSegments.join(' ')} fill="none" stroke={lineStroke} strokeWidth="2.5" />
      )}

      {points.map((pt, idx) => {
        const x = xForIdx(idx);
        const y = yForVal(pt.value);
        return (
          <g key={`rec-${idx}`}>
            <circle cx={x} cy={y} r={4.5} fill={lineStroke} />
            <text
              x={x}
              y={height - 12}
              textAnchor="middle"
              fontSize="10"
              fill={textFill}
              className="font-mono tabular-nums"
            >
              {pt.label}
            </text>
          </g>
        );
      })}

      {claims.map((cl, idx) => {
        const slotIdx = points.length + idx;
        const x = xForIdx(slotIdx);
        const y = yForVal(cl.value);
        return (
          <g key={`claim-${cl.id}`}>
            <circle cx={x} cy={y} r={5.5} fill="#d97706" />
            <text
              x={x}
              y={y - 10}
              textAnchor="middle"
              fontSize="10"
              fill="#d97706"
              className="font-mono tabular-nums"
            >
              claim: {cl.value}
            </text>
            <text
              x={x}
              y={height - 12}
              textAnchor="middle"
              fontSize="10"
              fill="#d97706"
              className="font-mono tabular-nums"
            >
              @{cl.author}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export default function App() {
  const [dark, setDark] = useState(false);
  const [activeTab, setActiveTab] = useState<'leaderboard' | 'launch' | 'sandbox' | 'files'>('leaderboard');
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  const [globalRows, setGlobalRows] = useState<GlobalRow[]>([]);
  const [indexChallenges, setIndexChallenges] = useState<IndexChallenge[]>([]);
  const [challengeDetails, setChallengeDetails] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  // Leaderboard filters & sorting
  const [tagFilter, setTagFilter] = useState<string>('all');
  const [evidenceFilter, setEvidenceFilter] = useState<string>('all');
  const [recent7dOnly, setRecent7dOnly] = useState<boolean>(false);
  const [sortBy, setSortBy] = useState<'last_improved' | 'contributors' | 'newest'>('last_improved');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Copy states
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // CLI Sandbox state
  const [cliOutput, setCliOutput] = useState<string>('');
  const [cliRunning, setCliRunning] = useState<boolean>(false);
  const [lastActionLabel, setLastActionLabel] = useState<string>('sar --help');
  const [sandboxCode, setSandboxCode] = useState<string>(
    `def sort_integers(data: list[int]) -> list[int]:\n    """Fast Timsort implementation beating the pure-Python merge sort baseline."""\n    out = list(data)\n    out.sort()\n    return out\n`
  );
  const [sandboxClaimed, setSandboxClaimed] = useState<string>('0.008');

  // File inspector state
  const [fileList, setFileList] = useState<Array<{ path: string; group: string }>>([]);
  const [selectedFilePath, setSelectedFilePath] = useState<string>('donate.md');
  const [selectedFileContent, setSelectedFileContent] = useState<string>('');

  // Launch interactive configurator state
  const [newSlug, setNewSlug] = useState<string>('matrix-rank-bound');
  const [newType, setNewType] = useState<'script' | 'lean' | 'manual'>('lean');
  const [newOwner, setNewOwner] = useState<string>('alice');

  useEffect(() => {
    fetch('/api/hub')
      .then((r) => r.json())
      .then((data) => {
        setGlobalRows(data.global?.challenges || []);
        setIndexChallenges(data.index?.challenges || []);
        setChallengeDetails(data.details || {});
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (activeTab === 'files') {
      fetch(`/api/files?path=${encodeURIComponent(selectedFilePath)}`)
        .then((r) => r.json())
        .then((data) => {
          if (data.files) setFileList(data.files);
          if (typeof data.content === 'string') setSelectedFileContent(data.content);
        })
        .catch(() => {});
    }
  }, [activeTab, selectedFilePath]);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId((prev) => (prev === id ? null : prev)), 1600);
  };

  const runCliAction = async (action: string, label: string, extra?: Record<string, any>) => {
    setCliRunning(true);
    setLastActionLabel(label);
    try {
      const res = await fetch('/api/sar/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...(extra || {}) }),
      });
      const data = await res.json();
      setCliOutput(
        [
          `$ ${label}`,
          data.stdout || '',
          data.stderr ? `\n[stderr]\n${data.stderr}` : '',
          `\n[exit code: ${data.code ?? 0}]`,
        ]
          .filter(Boolean)
          .join('\n')
      );
      if (action === 'sync' || action === 'check-frontier') {
        const hubRes = await fetch('/api/hub').then((r) => r.json());
        setGlobalRows(hubRes.global?.challenges || []);
        setIndexChallenges(hubRes.index?.challenges || []);
        setChallengeDetails(hubRes.details || {});
      }
    } catch (err: any) {
      setCliOutput(`Error executing ${label}: ${err.message}`);
    } finally {
      setCliRunning(false);
    }
  };

  const runLiveVerify = async () => {
    setCliRunning(true);
    setLastActionLabel('sar verify submissions/alice-custom --no-docker --json');
    try {
      const res = await fetch('/api/sar/verify-sandbox', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: sandboxCode,
          claimed: parseFloat(sandboxClaimed) || 0.01,
          author: 'alice',
        }),
      });
      const data = await res.json();
      setCliOutput(
        `$ sar verify submissions/alice-custom --no-docker --json\n${data.stdout || data.stderr || JSON.stringify(data, null, 2)}`
      );
    } catch (err: any) {
      setCliOutput(`Verification error: ${err.message}`);
    } finally {
      setCliRunning(false);
    }
  };

  const allTags = useMemo(() => {
    const s = new Set<string>();
    globalRows.forEach((r) => (r.tags || []).forEach((t) => s.add(t)));
    return Array.from(s).sort();
  }, [globalRows]);

  const filteredChallenges = useMemo(() => {
    const nowMs = new Date('2026-10-25T18:00:00Z').getTime();
    const rows = globalRows.filter((c) => {
      if (tagFilter !== 'all' && !(c.tags || []).includes(tagFilter)) return false;
      if (evidenceFilter !== 'all') {
        const ev = formatEvidenceLabel(c.verifier_type, c.current_best?.evidence);
        if (ev !== evidenceFilter) return false;
      }
      if (recent7dOnly) {
        if (!c.last_improved) return false;
        const diffDays = (nowMs - new Date(c.last_improved).getTime()) / (1000 * 3600 * 24);
        if (diffDays > 7) return false;
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchTitle = c.title.toLowerCase().includes(q);
        const matchSlug = c.slug.toLowerCase().includes(q);
        const matchTag = (c.tags || []).some((t) => t.toLowerCase().includes(q));
        if (!matchTitle && !matchSlug && !matchTag) return false;
      }
      return true;
    });

    rows.sort((a, b) => {
      if (sortBy === 'contributors') return (b.contributors || 0) - (a.contributors || 0);
      if (sortBy === 'newest') return b.slug.localeCompare(a.slug);
      return String(b.last_improved || '').localeCompare(String(a.last_improved || ''));
    });

    return rows;
  }, [globalRows, tagFilter, evidenceFilter, recent7dOnly, sortBy, searchQuery]);

  const selectedChallengeRow = useMemo(
    () => globalRows.find((r) => r.slug === selectedSlug) || null,
    [globalRows, selectedSlug]
  );
  const selectedChallengeIndex = useMemo(
    () => indexChallenges.find((c) => c.slug === selectedSlug) || null,
    [indexChallenges, selectedSlug]
  );
  const selectedChallengeDetail = selectedSlug ? challengeDetails[selectedSlug] : null;

  const canonicalDonatePrompt =
    'Read https://github.com/superautoresearch/hub/blob/main/donate.md and follow it.';
  const canonicalLaunchPrompt =
    'Read https://github.com/superautoresearch/hub/blob/main/launch.md and follow it.';

  return (
    <div
      className={
        dark
          ? 'min-h-screen bg-slate-950 text-slate-100 transition-colors duration-150'
          : 'min-h-screen bg-white text-slate-900 transition-colors duration-150'
      }
    >
      {/* Top Bar Contract: 3 zones separated by gap-8 */}
      <header
        className={`flex items-center justify-between gap-8 px-6 py-4 border-b ${
          dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'
        }`}
      >
        {/* Zone 1: Brand mark + wordmark */}
        <button
          type="button"
          onClick={() => {
            setSelectedSlug(null);
            setActiveTab('leaderboard');
          }}
          className="inline-flex items-center gap-2.5 text-lg font-bold tracking-tight whitespace-nowrap shrink-0 cursor-pointer"
        >
          <img
            src={logoUrl}
            alt="superAutoResearch logo"
            className="w-7 h-7 rounded-md object-cover shrink-0"
            referrerPolicy="no-referrer"
          />
          <span>superAutoResearch</span>
        </button>

        {/* Zone 2: 4 concise single-line text navigation links */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          <button
            type="button"
            onClick={() => {
              setSelectedSlug(null);
              setActiveTab('leaderboard');
            }}
            className={`whitespace-nowrap shrink-0 cursor-pointer transition-colors ${
              activeTab === 'leaderboard' && !selectedSlug
                ? 'underline underline-offset-4 font-semibold'
                : dark
                ? 'text-slate-400 hover:text-slate-100'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Leaderboard
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedSlug(null);
              setActiveTab('launch');
            }}
            className={`whitespace-nowrap shrink-0 cursor-pointer transition-colors ${
              activeTab === 'launch'
                ? 'underline underline-offset-4 font-semibold'
                : dark
                ? 'text-slate-400 hover:text-slate-100'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Launch Challenge
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedSlug(null);
              setActiveTab('sandbox');
              if (!cliOutput) runCliAction('help', 'sar --help');
            }}
            className={`whitespace-nowrap shrink-0 cursor-pointer transition-colors ${
              activeTab === 'sandbox'
                ? 'underline underline-offset-4 font-semibold'
                : dark
                ? 'text-slate-400 hover:text-slate-100'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            CLI & Verifier
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedSlug(null);
              setActiveTab('files');
            }}
            className={`whitespace-nowrap shrink-0 cursor-pointer transition-colors ${
              activeTab === 'files'
                ? 'underline underline-offset-4 font-semibold'
                : dark
                ? 'text-slate-400 hover:text-slate-100'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Hub Files
          </button>
        </nav>

        {/* Zone 3: 1 primary action */}
        <div className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={() => setDark(!dark)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-xs font-medium rounded-lg border transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
              dark
                ? 'border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800'
                : 'border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
            }`}
          >
            {dark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            {dark ? 'Light Theme' : 'Dark Theme'}
          </button>
        </div>
      </header>

      {/* Mobile navigation strip */}
      <div
        className={`flex md:hidden items-center gap-4 px-4 py-2.5 border-b overflow-x-auto text-xs font-medium ${
          dark ? 'border-slate-800 bg-slate-900/50' : 'border-slate-200 bg-slate-50'
        }`}
      >
        <button
          type="button"
          onClick={() => {
            setSelectedSlug(null);
            setActiveTab('leaderboard');
          }}
          className="whitespace-nowrap shrink-0"
        >
          Leaderboard
        </button>
        <button
          type="button"
          onClick={() => {
            setSelectedSlug(null);
            setActiveTab('launch');
          }}
          className="whitespace-nowrap shrink-0"
        >
          Launch Challenge
        </button>
        <button
          type="button"
          onClick={() => {
            setSelectedSlug(null);
            setActiveTab('sandbox');
            if (!cliOutput) runCliAction('help', 'sar --help');
          }}
          className="whitespace-nowrap shrink-0"
        >
          CLI & Verifier
        </button>
        <button
          type="button"
          onClick={() => {
            setSelectedSlug(null);
            setActiveTab('files');
          }}
          className="whitespace-nowrap shrink-0"
        >
          Hub Files
        </button>
      </div>

      <main className="max-w-[1240px] mx-auto px-4 sm:px-6 py-8">
        {/* VIEW 1: CHALLENGE DETAIL (/c/<slug>) */}
        {selectedSlug && selectedChallengeRow ? (
          <div className="space-y-8">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <button
                type="button"
                onClick={() => setSelectedSlug(null)}
                className={`text-sm font-medium cursor-pointer hover:underline ${
                  dark ? 'text-slate-400 hover:text-slate-100' : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                ← Back to global leaderboard
              </button>
              <div className="flex items-center gap-3 text-xs">
                <a
                  href={selectedChallengeRow.repo_url}
                  target="_blank"
                  rel="noreferrer"
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border font-medium whitespace-nowrap shrink-0 ${
                    dark
                      ? 'border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800'
                      : 'border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  Repository <ExternalLink className="w-3.5 h-3.5" />
                </a>
                <a
                  href={selectedChallengeIndex?.agents_md_url || `${selectedChallengeRow.repo_url}/blob/main/AGENTS.md`}
                  target="_blank"
                  rel="noreferrer"
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border font-medium whitespace-nowrap shrink-0 ${
                    dark
                      ? 'border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800'
                      : 'border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  AGENTS.md <ExternalLink className="w-3.5 h-3.5" />
                </a>
                <a
                  href={selectedChallengeIndex?.attempt_log_url || `${selectedChallengeRow.repo_url}/issues/1`}
                  target="_blank"
                  rel="noreferrer"
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border font-medium whitespace-nowrap shrink-0 ${
                    dark
                      ? 'border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800'
                      : 'border-slate-200 bg-slate-50 text-slate-800 hover:bg-slate-100'
                  }`}
                >
                  Attempt Log <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            {/* Challenge Header & Donate Prompt */}
            <section
              className={`p-6 rounded-lg border ${
                dark ? 'border-slate-800 bg-slate-900/60' : 'border-slate-200 bg-slate-50/70'
              }`}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-4">
                <div>
                  <h1 className="text-2xl font-bold tracking-tight">{selectedChallengeRow.title}</h1>
                  <p className={`mt-1 text-sm ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                    {selectedChallengeRow.summary}
                  </p>
                </div>
                <div className={`text-xs font-mono ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                  <span>{selectedChallengeRow.repo}</span>
                  <span className="mx-2">·</span>
                  <span>verifier: {selectedChallengeRow.verifier_type}</span>
                  <span className="mx-2">·</span>
                  <span>
                    metric: {selectedChallengeRow.metric.name} ({selectedChallengeRow.metric.direction})
                  </span>
                </div>
              </div>

              <div className="mt-5">
                <div className={`text-xs font-medium mb-1.5 ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Donate leftover tokens to this challenge:
                </div>
                <div
                  className={`flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-md border ${
                    dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'
                  }`}
                >
                  <code className="text-xs sm:text-sm overflow-x-auto whitespace-nowrap">
                    {`${canonicalDonatePrompt} challenge: ${selectedChallengeRow.slug}`}
                  </code>
                  <button
                    type="button"
                    onClick={() =>
                      copyToClipboard(
                        `${canonicalDonatePrompt} challenge: ${selectedChallengeRow.slug}`,
                        `donate-${selectedChallengeRow.slug}`
                      )
                    }
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded border whitespace-nowrap shrink-0 cursor-pointer ${
                      dark
                        ? 'border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-200'
                        : 'border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-800'
                    }`}
                  >
                    {copiedId === `donate-${selectedChallengeRow.slug}` ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-emerald-500" /> Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" /> Copy Prompt
                      </>
                    )}
                  </button>
                </div>
              </div>
            </section>

            {/* Chart + Open Tracks Split */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div
                className={`lg:col-span-7 p-6 rounded-lg border ${
                  dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                }`}
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-base font-semibold">
                    Record History ({selectedChallengeRow.metric.name})
                  </h2>
                  <div className={`text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                    <span>Step line: verified records</span>
                    <span className="mx-2">·</span>
                    <span>Amber dots: open claims</span>
                  </div>
                </div>
                <RecordStepChart
                  baselineValue={selectedChallengeRow.baseline.value}
                  records={selectedChallengeDetail?.records || []}
                  claims={selectedChallengeDetail?.claims || []}
                  metric={selectedChallengeRow.metric}
                  dark={dark}
                />
              </div>

              <div
                className={`lg:col-span-5 p-6 rounded-lg border ${
                  dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                }`}
              >
                <h2 className="text-base font-semibold mb-1">
                  Open Tracks ({(selectedChallengeIndex?.open_tracks || selectedChallengeDetail?.tracks || []).length})
                </h2>
                <p className={`text-xs mb-4 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                  Sub-tasks unclaimed in the last 24h. Claim a track via <code>sar claim</code> before starting work.
                </p>
                <div className="divide-y divide-slate-200 dark:divide-slate-800">
                  {(selectedChallengeIndex?.open_tracks || selectedChallengeDetail?.tracks || []).map(
                    (track: TrackItem) => {
                      const claimCmd = `sar claim --challenge ${selectedChallengeRow.slug} --track ${track.id}`;
                      return (
                        <div key={track.id} className="py-3 first:pt-0 last:pb-0">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-mono text-xs font-semibold">{track.id}</span>
                            <button
                              type="button"
                              onClick={() => copyToClipboard(claimCmd, `track-${track.id}`)}
                              className={`text-xs font-mono px-2 py-0.5 rounded border cursor-pointer whitespace-nowrap shrink-0 ${
                                dark
                                  ? 'border-slate-700 text-slate-300 hover:bg-slate-800'
                                  : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                              }`}
                            >
                              {copiedId === `track-${track.id}` ? 'Copied sar claim' : 'Copy sar claim'}
                            </button>
                          </div>
                          <div className="text-sm font-medium mt-1">{track.title}</div>
                          {track.notes && (
                            <div className={`text-xs mt-1 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                              {track.notes}
                            </div>
                          )}
                        </div>
                      );
                    }
                  )}
                </div>
              </div>
            </div>

            {/* Record Chain Table */}
            <section
              className={`rounded-lg border overflow-hidden ${
                dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
              }`}
            >
              <div className={`px-6 py-4 border-b ${dark ? 'border-slate-800' : 'border-slate-200'}`}>
                <h2 className="text-base font-semibold">Verified Record Chain</h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr
                      className={`border-b text-xs font-semibold ${
                        dark
                          ? 'border-slate-800 bg-slate-900 text-slate-400'
                          : 'border-slate-200 bg-slate-50 text-slate-600'
                      }`}
                    >
                      <th className="py-3 px-4">#</th>
                      <th className="py-3 px-4">Record</th>
                      <th className="py-3 px-4">Holder</th>
                      <th className="py-3 px-4">Agent · Model (self-reported)</th>
                      <th className="py-3 px-4">Evidence</th>
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4 text-right">PR</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    <tr>
                      <td className="py-3 px-4 font-mono tabular-nums text-xs">0</td>
                      <td className="py-3 px-4 font-mono tabular-nums">
                        <MetricDisplay
                          value={selectedChallengeRow.baseline.value}
                          metric={selectedChallengeRow.metric}
                        />
                      </td>
                      <td className="py-3 px-4 text-xs">
                        Baseline ({selectedChallengeRow.baseline.label})
                      </td>
                      <td className={`py-3 px-4 text-xs ${dark ? 'text-slate-500' : 'text-slate-400'}`}>
                        —
                      </td>
                      <td className="py-3 px-4 text-xs">Baseline</td>
                      <td className={`py-3 px-4 font-mono tabular-nums text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                        —
                      </td>
                      <td className="py-3 px-4 text-right text-xs">—</td>
                    </tr>
                    {(selectedChallengeDetail?.records || []).map((rec: RecordEntry, idx: number) => (
                      <tr key={rec.id}>
                        <td className="py-3 px-4 font-mono tabular-nums text-xs">{idx + 1}</td>
                        <td className="py-3 px-4 font-mono tabular-nums font-semibold">
                          <MetricDisplay value={rec.value} metric={selectedChallengeRow.metric} />
                        </td>
                        <td className="py-3 px-4 font-mono text-xs">@{rec.author}</td>
                        <td className={`py-3 px-4 text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                          {[rec.agent, rec.model].filter(Boolean).join(' · ') || '—'}
                        </td>
                        <td className="py-3 px-4 text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                          {formatEvidenceLabel(selectedChallengeRow.verifier_type, rec.evidence)}
                        </td>
                        <td className={`py-3 px-4 font-mono tabular-nums text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                          {(rec.date || '').slice(0, 10)}
                        </td>
                        <td className="py-3 px-4 text-right font-mono tabular-nums text-xs">
                          {rec.url ? (
                            <a
                              href={rec.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-sky-600 dark:text-sky-400 hover:underline"
                            >
                              #{rec.pr || idx + 1}
                            </a>
                          ) : rec.pr ? (
                            `#${rec.pr}`
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        ) : activeTab === 'leaderboard' ? (
          /* VIEW 2: GLOBAL LEADERBOARD (/) */
          <div className="space-y-8">
            {/* Top Donate Prompt Banner */}
            <section
              className={`p-6 rounded-lg border ${
                dark ? 'border-slate-800 bg-slate-900/60' : 'border-slate-200 bg-slate-50/70'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                <div>
                  <h1 className="text-xl sm:text-2xl font-bold tracking-tight" style={{ textWrap: 'balance' }}>
                    Open Research Challenge Hub & Global Leaderboard
                  </h1>
                  <p className={`text-sm mt-1 ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                    Donate leftover LLM tokens with one prompt, or launch a measurable research challenge in its own GitHub repository.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('launch')}
                  className={`inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                    dark
                      ? 'bg-slate-100 text-slate-950 hover:bg-white'
                      : 'bg-slate-900 text-white hover:bg-slate-800'
                  }`}
                >
                  Launch a challenge <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              <div
                className={`flex items-center justify-between gap-3 px-4 py-3 rounded-md border ${
                  dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'
                }`}
              >
                <code className="text-xs sm:text-sm overflow-x-auto whitespace-nowrap">
                  {canonicalDonatePrompt}
                </code>
                <button
                  type="button"
                  onClick={() => copyToClipboard(canonicalDonatePrompt, 'global-donate')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded border whitespace-nowrap shrink-0 cursor-pointer ${
                    dark
                      ? 'border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-200'
                      : 'border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-800'
                  }`}
                >
                  {copiedId === 'global-donate' ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-500" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy Donate Prompt
                    </>
                  )}
                </button>
              </div>
            </section>

            {/* Filter & Sort Controls Bar */}
            <section className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3">
                {/* Search */}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter challenges..."
                    className={`pl-8 pr-3 py-1.5 text-xs rounded-md border ${
                      dark
                        ? 'border-slate-800 bg-slate-900 text-slate-100 placeholder:text-slate-500'
                        : 'border-slate-200 bg-white text-slate-900 placeholder:text-slate-400'
                    }`}
                  />
                </div>

                {/* Tag Selector */}
                <select
                  aria-label="Filter by tag"
                  value={tagFilter}
                  onChange={(e) => setTagFilter(e.target.value)}
                  className={`px-3 py-1.5 text-xs rounded-md border ${
                    dark
                      ? 'border-slate-800 bg-slate-900 text-slate-200'
                      : 'border-slate-200 bg-white text-slate-800'
                  }`}
                >
                  <option value="all">All tags</option>
                  {allTags.map((t) => (
                    <option key={t} value={t}>
                      tag: {t}
                    </option>
                  ))}
                </select>

                {/* Segmented Evidence Filter */}
                <div
                  className={`flex items-center gap-1 p-1 rounded-lg border ${
                    dark ? 'bg-slate-900 border-slate-800' : 'bg-slate-100 border-slate-200/70'
                  }`}
                >
                  {(['all', 'Lean verified', 'Verified', 'Human verified'] as const).map((ev) => (
                    <button
                      key={ev}
                      type="button"
                      onClick={() => setEvidenceFilter(ev)}
                      className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 cursor-pointer ${
                        evidenceFilter === ev
                          ? dark
                            ? 'bg-slate-800 text-white shadow-xs'
                            : 'bg-white text-slate-900 shadow-xs'
                          : dark
                          ? 'text-slate-400 hover:text-slate-200'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      {ev === 'all' ? 'All Evidence' : ev}
                    </button>
                  ))}
                </div>

                {/* Improved in last 7 days */}
                <label className="inline-flex items-center gap-2 text-xs cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={recent7dOnly}
                    onChange={(e) => setRecent7dOnly(e.target.checked)}
                    className="rounded border-slate-300"
                  />
                  <span>Improved in last 7 days</span>
                </label>
              </div>

              {/* Sort selector */}
              <div className="flex items-center gap-2 text-xs">
                <span className={dark ? 'text-slate-400' : 'text-slate-500'}>Sort:</span>
                <select
                  aria-label="Sort challenges"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className={`px-3 py-1.5 text-xs rounded-md border ${
                    dark
                      ? 'border-slate-800 bg-slate-900 text-slate-200'
                      : 'border-slate-200 bg-white text-slate-800'
                  }`}
                >
                  <option value="last_improved">Last improved</option>
                  <option value="contributors">Contributors</option>
                  <option value="newest">Newest</option>
                </select>
              </div>
            </section>

            {/* Global Leaderboard Table */}
            <section
              className={`rounded-lg border overflow-hidden ${
                dark ? 'border-slate-800 bg-slate-900/30' : 'border-slate-200 bg-white'
              }`}
            >
              {loading ? (
                <div className="p-8 text-center text-sm text-slate-500">Loading challenges...</div>
              ) : filteredChallenges.length === 0 ? (
                <div className="p-10 text-center space-y-3">
                  <div className="text-sm font-medium">No challenges match the active filters.</div>
                  <button
                    type="button"
                    onClick={() => {
                      setTagFilter('all');
                      setEvidenceFilter('all');
                      setRecent7dOnly(false);
                      setSearchQuery('');
                    }}
                    className="px-3 py-1.5 text-xs font-medium rounded border border-slate-300 dark:border-slate-700 cursor-pointer"
                  >
                    Reset Filters
                  </button>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr
                        className={`border-b text-xs font-semibold ${
                          dark
                            ? 'border-slate-800 bg-slate-900 text-slate-400'
                            : 'border-slate-200 bg-slate-50 text-slate-600'
                        }`}
                      >
                        <th className="py-3.5 px-4">Challenge</th>
                        <th className="py-3.5 px-4 text-right">Baseline</th>
                        <th className="py-3.5 px-4 text-right">First record</th>
                        <th className="py-3.5 px-4 text-right">Current best</th>
                        <th className="py-3.5 px-4">Holder</th>
                        <th className="py-3.5 px-4">Evidence</th>
                        <th className="py-3.5 px-4">Last improved</th>
                        <th className="py-3.5 px-4 text-right">Records</th>
                        <th className="py-3.5 px-4 text-right">Contributors</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {filteredChallenges.map((c) => {
                        const best = c.current_best;
                        const first = c.first_record;
                        const evLabel = best
                          ? formatEvidenceLabel(c.verifier_type, best.evidence)
                          : 'Baseline';

                        return (
                          <React.Fragment key={c.slug}>
                            <tr
                              onClick={() => setSelectedSlug(c.slug)}
                              className={`cursor-pointer transition-colors ${
                                dark ? 'hover:bg-slate-900/80' : 'hover:bg-slate-50'
                              }`}
                            >
                              <td className="py-3.5 px-4">
                                <div className="font-semibold">{c.title}</div>
                                {/* Zero-Pill unboxed metadata with typographic separators */}
                                <div className={`text-xs mt-0.5 ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                                  <span>{c.kind}</span>
                                  <span aria-hidden="true"> · </span>
                                  <span>{(c.tags || []).join(' · ')}</span>
                                </div>
                                {c.status === 'statement-changed' && (
                                  <div className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 font-medium mt-1">
                                    <AlertTriangle className="w-3.5 h-3.5" /> statement-changed
                                  </div>
                                )}
                                {c.status === 'unreachable' && (
                                  <div className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium mt-1">
                                    <AlertTriangle className="w-3.5 h-3.5" /> unreachable
                                  </div>
                                )}
                              </td>
                              <td className="py-3.5 px-4 text-right font-mono tabular-nums text-xs">
                                <MetricDisplay value={c.baseline?.value} metric={c.metric} />
                              </td>
                              <td className="py-3.5 px-4 text-right font-mono tabular-nums text-xs">
                                {first ? <MetricDisplay value={first.value} metric={c.metric} /> : '—'}
                              </td>
                              <td className="py-3.5 px-4 text-right font-mono tabular-nums font-semibold">
                                {best ? (
                                  <MetricDisplay value={best.value} metric={c.metric} />
                                ) : (
                                  <MetricDisplay value={c.baseline?.value} metric={c.metric} />
                                )}
                              </td>
                              <td className="py-3.5 px-4">
                                {best ? (
                                  <div>
                                    <span className="font-mono text-xs font-medium">@{best.author}</span>
                                    {(best.agent || best.model) && (
                                      <div className={`text-xs ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                                        {[best.agent, best.model].filter(Boolean).join(' · ')}{' '}
                                        <span className="italic">(self-reported)</span>
                                      </div>
                                    )}
                                  </div>
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="py-3.5 px-4 text-xs font-medium text-emerald-700 dark:text-emerald-400 whitespace-nowrap">
                                {evLabel}
                              </td>
                              <td className={`py-3.5 px-4 font-mono tabular-nums text-xs whitespace-nowrap ${dark ? 'text-slate-400' : 'text-slate-500'}`}>
                                {(c.last_improved || '—').slice(0, 10)}
                              </td>
                              <td className="py-3.5 px-4 text-right font-mono tabular-nums text-xs">
                                {c.records_count}
                              </td>
                              <td className="py-3.5 px-4 text-right font-mono tabular-nums text-xs">
                                {c.contributors}
                              </td>
                            </tr>

                            {/* Muted Claimed sub-row when best_claim beats current_best */}
                            {c.best_claim && (
                              <tr
                                onClick={() => setSelectedSlug(c.slug)}
                                className={`cursor-pointer text-xs ${
                                  dark
                                    ? 'bg-slate-900/90 text-slate-400 hover:bg-slate-900'
                                    : 'bg-slate-50/90 text-slate-600 hover:bg-slate-100/70'
                                }`}
                              >
                                <td className="py-2 px-4 pl-8" colSpan={3}>
                                  ↳ Unverified claim <span className="font-mono">{c.best_claim.id}</span> beating current best
                                </td>
                                <td className="py-2 px-4 text-right font-mono tabular-nums font-medium text-amber-600 dark:text-amber-400">
                                  <MetricDisplay value={c.best_claim.value} metric={c.metric} />
                                </td>
                                <td className="py-2 px-4 font-mono">
                                  @{c.best_claim.author}
                                  {c.best_claim.model ? ` · ${c.best_claim.model}` : ''}
                                </td>
                                <td className="py-2 px-4 text-amber-600 dark:text-amber-400 font-medium">
                                  Claimed (PR #{c.best_claim.pr || '—'})
                                </td>
                                <td className="py-2 px-4 font-mono tabular-nums">
                                  {(c.best_claim.date || '').slice(0, 10)}
                                </td>
                                <td className="py-2 px-4 text-right" colSpan={2}>
                                  Awaiting verifier / review
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        ) : activeTab === 'launch' ? (
          /* VIEW 3: LAUNCH CHALLENGE (/launch) */
          <div className="space-y-8">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Launch a Research Challenge</h1>
              <p className={`mt-1 text-sm ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                Every challenge is a standalone public GitHub repository registered in <code>superautoresearch/hub</code> by Pull Request.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div
                className={`p-6 rounded-lg border ${
                  dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                }`}
              >
                <div className="text-xs font-semibold text-sky-600 dark:text-sky-400 mb-1">
                  01. Any Coding Agent
                </div>
                <h2 className="text-base font-semibold mb-2">Copy-Paste Launch Prompt</h2>
                <p className={`text-xs mb-4 ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Point any agent at <code>launch.md</code>. It interviews you (≤6 questions), scaffolds the repo, verifies the baseline, and opens the hub PR.
                </p>
                <div
                  className={`p-3 rounded border font-mono text-xs overflow-x-auto mb-3 ${
                    dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  {canonicalLaunchPrompt}
                </div>
                <button
                  type="button"
                  onClick={() => copyToClipboard(canonicalLaunchPrompt, 'launch-prompt')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded border cursor-pointer ${
                    dark
                      ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  {copiedId === 'launch-prompt' ? 'Copied' : 'Copy Launch Prompt'}
                </button>
              </div>

              <div
                className={`p-6 rounded-lg border ${
                  dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                }`}
              >
                <div className="text-xs font-semibold text-sky-600 dark:text-sky-400 mb-1">
                  02. Claude Code Plugin
                </div>
                <h2 className="text-base font-semibold mb-2">Install Marketplace Skills</h2>
                <p className={`text-xs mb-4 ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Exposes the <code>new-challenge</code>, <code>register-repo</code>, and <code>donate</code> skills directly inside Claude Code.
                </p>
                <pre
                  className={`p-3 rounded border font-mono text-xs overflow-x-auto ${
                    dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-slate-50'
                  }`}
                >{`/plugin marketplace add superautoresearch/hub\n/plugin install superautoresearch`}</pre>
              </div>

              <div
                className={`p-6 rounded-lg border ${
                  dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                }`}
              >
                <div className="text-xs font-semibold text-sky-600 dark:text-sky-400 mb-1">
                  03. Manual CLI Workflow
                </div>
                <h2 className="text-base font-semibold mb-2">Scaffold with sar CLI</h2>
                <p className={`text-xs mb-4 ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Use the zero-heavy-dependency Python <code>sar</code> CLI to scaffold, validate, verify, publish, and register.
                </p>
                <div className="space-y-2 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      type="text"
                      value={newSlug}
                      onChange={(e) => setNewSlug(e.target.value)}
                      placeholder="slug"
                      className={`px-2.5 py-1.5 rounded border font-mono text-xs ${
                        dark ? 'border-slate-700 bg-slate-950' : 'border-slate-200 bg-slate-50'
                      }`}
                    />
                    <select
                      value={newType}
                      onChange={(e) => setNewType(e.target.value as any)}
                      className={`px-2.5 py-1.5 rounded border font-mono text-xs ${
                        dark ? 'border-slate-700 bg-slate-950' : 'border-slate-200 bg-slate-50'
                      }`}
                    >
                      <option value="script">type: script</option>
                      <option value="lean">type: lean</option>
                      <option value="manual">type: manual</option>
                    </select>
                  </div>
                  <pre
                    className={`p-3 rounded border font-mono text-xs overflow-x-auto ${
                      dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-slate-50'
                    }`}
                  >{`sar new ${newSlug || 'my-challenge'} --type ${newType} --owner ${newOwner}\ncd ${newSlug || 'my-challenge'}\nsar validate .\nsar verify statement/baseline\nsar init-github --public\nsar register`}</pre>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab('sandbox');
                      runCliAction(
                        'register-preview',
                        `sar register --dry-run (${newSlug || 'matrix-rank-bound'})`,
                        { slug: newSlug || 'matrix-rank-bound', type: newType, owner: newOwner }
                      );
                    }}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded border cursor-pointer ${
                      dark
                        ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                        : 'border-slate-200 bg-white hover:bg-slate-50'
                    }`}
                  >
                    <Play className="w-3.5 h-3.5" /> Preview Hub Registration PR (sar register --dry-run)
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : activeTab === 'sandbox' ? (
          /* VIEW 4: LIVE SAR CLI & VERIFIER SANDBOX (/sandbox) */
          <div className="space-y-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Live sar CLI & Verifier Sandbox</h1>
                <p className={`mt-1 text-sm ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Execute real <code>sar</code> CLI commands, run the unit test suite (Milestones 1–7) and end-to-end dry run (Milestone 8), or test a custom Python sorting submission against the automated verifier.
                </p>
              </div>
              <div
                className={`flex items-center gap-1 p-1 rounded-lg border ${
                  dark ? 'bg-slate-900 border-slate-800' : 'bg-slate-100 border-slate-200/70'
                }`}
              >
                <button
                  type="button"
                  onClick={() => setActiveTab('sandbox')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer ${
                    dark ? 'bg-slate-800 text-white' : 'bg-white text-slate-900 shadow-2xs'
                  }`}
                >
                  CLI & Verifier
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('files')}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer ${
                    dark ? 'text-slate-400 hover:text-slate-200' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Hub Repository Files
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: CLI Actions + Live Submission Editor */}
              <div className="lg:col-span-6 space-y-6">
                <div
                  className={`p-5 rounded-lg border ${
                    dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                  }`}
                >
                  <h2 className="text-sm font-semibold mb-3">Run Hub CLI & Verification Milestones</h2>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('help', 'sar --help')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <Terminal className="w-3.5 h-3.5" /> sar --help
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('validate-registry', 'sar validate registry/3sum-exponent.toml --json')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> sar validate
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('sync', 'sar sync --hub .')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> sar sync
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('check-frontier', 'sar check-frontier --hub .')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800 text-sky-400'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100 text-sky-700'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> sar check-frontier
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('claim-preview', 'sar claim --challenge 3sum-exponent --track derandomize --dry-run')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> sar claim --dry-run
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('attempt-preview', 'sar attempt --challenge 3sum-exponent --track derandomize --result fail --dry-run')}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> sar attempt --dry-run
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() =>
                        runCliAction(
                          'register-preview',
                          `sar register --dry-run (${newSlug || 'matrix-rank-bound'})`,
                          { slug: newSlug || 'matrix-rank-bound', type: newType, owner: newOwner }
                        )
                      }
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono rounded border cursor-pointer ${
                        dark
                          ? 'border-slate-700 bg-slate-900 hover:bg-slate-800'
                          : 'border-slate-200 bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> sar register --dry-run
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('unit-tests', 'python3 -m unittest discover -s tests -v')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-sky-600 text-white hover:bg-sky-500 cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5" /> Run Unit Tests (M1–M7)
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('e2e-dry-run', 'bash tests/e2e_dry_run.sh')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-emerald-600 text-white hover:bg-emerald-500 cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5" /> Run E2E Dry Run (M8)
                    </button>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={() => runCliAction('push-github', 'git push -u origin main (superautoresearch/hub)')}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded bg-slate-900 dark:bg-slate-100 text-white dark:text-slate-950 hover:opacity-90 cursor-pointer"
                    >
                      <ExternalLink className="w-3.5 h-3.5" /> Push to superautoresearch/hub
                    </button>
                  </div>
                </div>

                {/* Interactive Verifier Submission Box */}
                <div
                  className={`p-5 rounded-lg border ${
                    dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-white'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-sm font-semibold">Interactive Script Verifier (`sar verify`)</h2>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() =>
                          setSandboxCode(
                            `def sort_integers(data: list[int]) -> list[int]:\n    out = list(data)\n    out.sort()\n    return out\n`
                          )
                        }
                        className="text-xs underline cursor-pointer"
                      >
                        Load Passing Solution
                      </button>
                      <span>·</span>
                      <button
                        type="button"
                        onClick={() =>
                          setSandboxCode(
                            `def sort_integers(data: list[int]) -> list[int]:\n    # Deliberately wrong output to trigger verifier rejection\n    return [0] * len(data)\n`
                          )
                        }
                        className="text-xs underline cursor-pointer text-amber-600 dark:text-amber-400"
                      >
                        Load Wrong Solution
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={sandboxCode}
                    onChange={(e) => setSandboxCode(e.target.value)}
                    rows={6}
                    className={`w-full p-3 rounded border font-mono text-xs ${
                      dark
                        ? 'border-slate-800 bg-slate-950 text-slate-100'
                        : 'border-slate-200 bg-slate-50 text-slate-900'
                    }`}
                  />
                  <div className="flex items-center justify-between gap-4 mt-3">
                    <label className="text-xs flex items-center gap-2">
                      <span>Claimed (s):</span>
                      <input
                        type="text"
                        value={sandboxClaimed}
                        onChange={(e) => setSandboxClaimed(e.target.value)}
                        className={`w-24 px-2 py-1 rounded border font-mono text-xs ${
                          dark ? 'border-slate-700 bg-slate-950' : 'border-slate-200 bg-white'
                        }`}
                      />
                    </label>
                    <button
                      type="button"
                      disabled={cliRunning}
                      onClick={runLiveVerify}
                      className={`inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg cursor-pointer ${
                        dark
                          ? 'bg-slate-100 text-slate-950 hover:bg-white'
                          : 'bg-slate-900 text-white hover:bg-slate-800'
                      }`}
                    >
                      <Play className="w-3.5 h-3.5" /> Run sar verify
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column: Live Terminal Output */}
              <div className="lg:col-span-6">
                <div
                  className={`rounded-lg border overflow-hidden h-full flex flex-col ${
                    dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-slate-900 text-slate-100'
                  }`}
                >
                  <div className="px-4 py-2.5 border-b border-slate-800 flex items-center justify-between text-xs font-mono text-slate-400">
                    <span>{lastActionLabel}</span>
                    <span>{cliRunning ? 'Executing...' : 'Idle'}</span>
                  </div>
                  <pre className="p-4 text-xs font-mono overflow-auto flex-1 max-h-[500px] leading-relaxed whitespace-pre-wrap">
                    {cliOutput || 'Select a command on the left to execute against the real Python sar CLI.'}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        ) : (
          /* VIEW 5: HUB ARCHITECTURE & FILES INSPECTOR (/files) */
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Hub Repository Files & Standalone Static Site</h1>
                <p className={`mt-1 text-sm ${dark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Inspect the generated repository layout (`registry/`, `templates/`, `skills/`, `.claude-plugin/`, `sar/`, `site/`, `.github/workflows/`).
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setActiveTab('cli')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md border cursor-pointer ${
                    dark
                      ? 'border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-200'
                      : 'border-slate-200 bg-white hover:bg-slate-50 text-slate-800'
                  }`}
                >
                  <Terminal className="w-3.5 h-3.5" /> CLI & Verifier
                </button>
                <a
                  href="/static-site/index.html"
                  target="_blank"
                  rel="noreferrer"
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md border whitespace-nowrap shrink-0 ${
                    dark
                      ? 'border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-200'
                      : 'border-slate-200 bg-slate-50 hover:bg-slate-100 text-slate-800'
                  }`}
                >
                  Open Standalone Static Site <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div
                className={`lg:col-span-4 rounded-lg border p-4 max-h-[580px] overflow-y-auto ${
                  dark ? 'border-slate-800 bg-slate-900/40' : 'border-slate-200 bg-slate-50/60'
                }`}
              >
                <div className="space-y-1">
                  {fileList.map((f) => (
                    <button
                      key={f.path}
                      type="button"
                      onClick={() => setSelectedFilePath(f.path)}
                      className={`w-full text-left px-3 py-2 rounded-md text-xs font-mono flex items-center justify-between gap-2 cursor-pointer ${
                        selectedFilePath === f.path
                          ? dark
                            ? 'bg-slate-800 text-white font-semibold'
                            : 'bg-white text-slate-900 font-semibold shadow-2xs border border-slate-200/80'
                          : dark
                          ? 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
                      }`}
                    >
                      <span className="truncate">{f.path}</span>
                      <span className="text-[10px] opacity-60 shrink-0">{f.group}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div
                className={`lg:col-span-8 rounded-lg border overflow-hidden flex flex-col ${
                  dark ? 'border-slate-800 bg-slate-950' : 'border-slate-200 bg-white'
                }`}
              >
                <div
                  className={`px-4 py-3 border-b flex items-center justify-between ${
                    dark ? 'border-slate-800 bg-slate-900/60' : 'border-slate-200 bg-slate-50'
                  }`}
                >
                  <div className="flex items-center gap-2 font-mono text-xs font-semibold">
                    <FileCode2 className="w-4 h-4" />
                    <span>{selectedFilePath}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(selectedFileContent, `file-${selectedFilePath}`)}
                    className="text-xs font-mono px-2.5 py-1 rounded border border-slate-300 dark:border-slate-700 cursor-pointer"
                  >
                    {copiedId === `file-${selectedFilePath}` ? 'Copied' : 'Copy File'}
                  </button>
                </div>
                <pre className="p-4 text-xs font-mono overflow-auto max-h-[520px] leading-relaxed">
                  {selectedFileContent}
                </pre>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer
        className={`mt-16 border-t py-6 text-xs ${
          dark ? 'border-slate-800 text-slate-500' : 'border-slate-200 text-slate-500'
        }`}
      >
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6 flex flex-wrap items-center justify-between gap-4">
          <span>
            superAutoResearch (<code>superautoresearch/hub</code>) · GitHub-native open research challenges · No points or cross-challenge people rankings
          </span>
          <div className="flex items-center gap-4">
            <a href="/generated/global.json" target="_blank" rel="noreferrer" className="hover:underline font-mono">
              generated/global.json
            </a>
            <a href="/generated/index.json" target="_blank" rel="noreferrer" className="hover:underline font-mono">
              generated/index.json
            </a>
            <a href="/static-site/index.html" target="_blank" rel="noreferrer" className="hover:underline font-mono">
              site/index.html
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
