"use client";

import { useMemo } from "react";
import type { ReactNode } from "react";

import type { AnalysisMode, Inference, ParseResponse } from "../lib/api";
import { buildReport, prettyCategory, TIER_META } from "../lib/report";
import styles from "./Report.module.css";

export interface ReportProps {
  parsed: ParseResponse;
  findings: Inference[];
  createdAt?: number;
  mode?: AnalysisMode;
}

function highlightEvidenceQuotes(content: string, quotes: string[]): ReactNode {
  const matches = quotes
    .filter(Boolean)
    .flatMap((quote) => {
      const ranges: Array<{ start: number; end: number }> = [];
      let cursor = 0;
      for (;;) {
        const start = content.indexOf(quote, cursor);
        if (start === -1) break;
        ranges.push({ start, end: start + quote.length });
        cursor = start + quote.length;
      }
      return ranges;
    })
    .sort((a, b) => a.start - b.start || b.end - a.end);

  const parts: ReactNode[] = [];
  let cursor = 0;
  let key = 0;

  for (const match of matches) {
    if (match.start < cursor) continue;
    if (match.start > cursor) {
      parts.push(content.slice(cursor, match.start));
    }
    parts.push(<mark key={`evidence-${key++}`}>{content.slice(match.start, match.end)}</mark>);
    cursor = match.end;
  }

  if (cursor === 0) return content;
  if (cursor < content.length) parts.push(content.slice(cursor));
  return parts;
}

export function Report({ parsed, findings, createdAt, mode = "conservative" }: ReportProps) {
  const data = useMemo(
    () => buildReport(parsed, findings, { createdAt }),
    [parsed, findings, createdAt],
  );

  const quotesByMessage = useMemo(() => {
    const quotes = new Map<string, string[]>();
    for (const finding of data.findings) {
      for (const ev of finding.evidence) {
        const existing = quotes.get(ev.message_id) ?? [];
        if (!existing.includes(ev.quote)) existing.push(ev.quote);
        quotes.set(ev.message_id, existing);
      }
    }
    return quotes;
  }, [data.findings]);

  const { totals, severity } = data;
  const modeLabel = mode === "speculative" ? "Speculative" : "Conservative";
  const lede =
    `This report summarises what a profiler could infer about you from ` +
    `${data.conversations.length} conversation${data.conversations.length === 1 ? "" : "s"} ` +
    `with an AI assistant. It found ${totals.findings} inference${totals.findings === 1 ? "" : "s"} ` +
    `across ${totals.categories} categor${totals.categories === 1 ? "y" : "ies"}` +
    (totals.sensitive > 0
      ? `, including ${totals.sensitive} that fall under special category data protected by GDPR Article 9.`
      : `.`);

  return (
    <div className={styles.page}>
      <div className={styles.sheet}>
        <div className={styles.toolbar}>
          <span className={styles.t}>Exposure report</span>
          <div className={styles.actions}>
            <a className={styles.back} href="/">
              ← New analysis
            </a>
            <button type="button" onClick={() => window.print()}>
              Save as PDF
            </button>
          </div>
        </div>

        <div className={styles.rp}>
          <div className={styles.brand}>
            <div className={styles.name}>
              Glass<span>house</span>
            </div>
            <div className={styles.stamp}>
              Exposure report
              <br />
              {data.date}
              <br />
              source: {data.source} export
              <br />
              mode: {modeLabel}
            </div>
          </div>

          <h1 className={styles.title}>What your conversations reveal about you</h1>
          <div className={mode === "speculative" ? `${styles.mode} ${styles.spec}` : styles.mode}>
            {modeLabel} mode
          </div>
          <p className={styles.lede}>{lede}</p>
          {mode === "speculative" && (
            <p className={styles.note}>
              Speculative mode intentionally includes broader profiling hypotheses from weaker signals.
              Treat these as plausible reads, not verified facts.
            </p>
          )}

          <div className={styles.band}>
            <div className={styles.score}>
              <div className={styles.n}>{data.score}</div>
              <div className={styles.l}>Leakage score</div>
            </div>
            <div>
              <span className={styles.pill} style={{ background: severity.tone }}>
                {severity.label}
              </span>
              <p>{severity.blurb}</p>
            </div>
          </div>

          <div className={styles.h}>
            Exposure by <b>tier</b>
          </div>
          {data.tierRows.map((row) => {
            const meta = TIER_META[row.tier];
            return (
              <div className={styles.tier} key={row.tier}>
                <div className={styles.nm}>
                  <i style={{ background: meta.accent }} />
                  Tier {row.tier}: {meta.short}
                </div>
                <div className={styles.bar}>
                  <span style={{ width: `${row.barPct}%`, background: meta.accent }} />
                </div>
                <div className={styles.num}>
                  <b>{row.count}</b> · {row.points} pts
                </div>
              </div>
            );
          })}

          {data.groups.length === 0 ? (
            <div className={styles.empty}>No inferences were extracted from these conversations.</div>
          ) : (
            data.groups.map((group) => (
              <section key={group.tier}>
                <div className={styles.h}>
                  Tier {group.tier} <b>{group.meta.label}</b>
                </div>
                {group.findings.map((f, i) => (
                  <div
                    className={styles.find}
                    key={i}
                    style={{ "--tc": group.meta.accent } as React.CSSProperties}
                  >
                    <div className={styles.top}>
                      <span
                        className={styles.cat}
                        style={{ background: group.meta.badgeBg, color: group.meta.badgeText }}
                      >
                        {prettyCategory(f.category_id)}
                      </span>
                      {f.subject === "third_party" && <span className={styles.tag}>third party</span>}
                      <span className={styles.claim}>{f.claim}</span>
                      <span className={styles.conf}>{f.confidence}</span>
                    </div>
                    {f.reasoning && <div className={styles.reason}>{f.reasoning}</div>}
                    {f.evidence.map((ev, j) => (
                      <div className={styles.q} key={j}>
                        <mark>{ev.quote}</mark>
                        <span className={styles.src}>from {data.labelOf(ev.message_id)}</span>
                      </div>
                    ))}
                  </div>
                ))}
              </section>
            ))
          )}

          <div className={styles.h}>
            What you can <b>do</b>
          </div>
          <div className={styles.rec}>
            {data.recommendations.map((rec, i) => (
              <div className={styles.item} key={i}>
                <i>{String(i + 1).padStart(2, "0")}</i>
                <span>{rec}</span>
              </div>
            ))}
          </div>

          <div className={styles.h}>
            How this tool <b>treats your data</b>
          </div>
          <div className={styles.gov}>
            <div className={styles.gh}>
              <span className={styles.b}>Governance</span> Built to inform you
            </div>
            <ul>
              <li>It analyses the conversations you uploaded, and only your messages within them.</li>
              <li>It does not build profiles of other people you mention.</li>
              <li>It makes inferences, not findings of fact, and each shows the sentence it came from.</li>
              <li>It does not decide anything about you and does not score you as a person.</li>
              <li>Your upload is processed for this report and not stored on our servers.</li>
              <li>Sensitive inferences are shown only so you can see your own exposure.</li>
            </ul>
            <div className={styles.law}>
              Privacy by design: purpose limitation, data minimisation, and transparency under the{" "}
              <b>GDPR</b>, and outside the prohibited and high-risk practices of the <b>EU AI Act</b> (no
              social scoring, no automated decisions about you, no third-party profiling).
            </div>
          </div>

          <div className={styles.foot}>
            Generated by Glasshouse, a research demonstration for the ML &amp; Society hackathon. Findings
            are inferences produced by a language model and are <b>not verified fact</b>. Some are wrong by
            design, which is part of what the tool demonstrates about automated profiling. Tier D maps to
            special category data under GDPR Article 9. This report is not legal advice.
          </div>

          <div className={styles.h}>
            Appendix <b>source transcript</b>
          </div>
          <div className={styles.appendix}>
            {data.conversations.map((conv) => (
              <div className={styles.conv} key={conv.conversation_id}>
                <div className={styles.convTitle}>{conv.title}</div>
                {conv.messages.map((m) => {
                  const quotes = quotesByMessage.get(m.id) ?? [];
                  const cited = quotes.length > 0;
                  return (
                    <div className={cited ? `${styles.msg} ${styles.cited}` : styles.msg} key={m.id}>
                      <div className={styles.who}>You · {data.labelOf(m.id)}</div>
                      {highlightEvidenceQuotes(m.content, quotes)}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
