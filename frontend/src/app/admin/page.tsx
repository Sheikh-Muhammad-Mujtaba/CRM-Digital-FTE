"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { clearAdminCredentials, getAdminCredentials } from "@/lib/admin-auth";

type DashboardResponse = {
  period_hours: number;
  generated_at: string;
  kpis: {
    tickets_total: number;
    tickets_open: number;
    messages_total: number;
    conversations_escalated: number;
    tickets_24h: number;
    messages_24h: number;
    escalations_24h: number;
    escalation_rate: number;
  };
  sentiments: {
    avg_score: number;
    total: number;
    positive: number;
    neutral: number;
    negative: number;
    source?: "final_outcome" | "heuristic_customer_message";
    recent_negative_examples: Array<{
      label: string;
      score: number;
      content: string;
      channel: string;
      conversation_id: string;
      created_at: string | null;
    }>;
  };
  channels: Array<{
    channel: string;
    inbound: number;
    outbound: number;
    total: number;
    status: "healthy" | "degraded" | "down";
  }>;
  recent_status_logs: Array<{
    timestamp: string | null;
    level: string;
    source: string;
    message: string;
    metadata: {
      channel?: string | null;
      sender_type?: string | null;
      conversation_id?: string | null;
      event_id?: string | null;
    };
  }>;
  recent_tickets: Array<{
    id: string;
    title: string;
    priority: string;
    status: string;
    created_at: string | null;
  }>;
};

type DashboardActivity = {
  period_hours: number;
  limit: number;
  count: number;
  generated_at: string;
  items: Array<{
    id: string;
    timestamp: string | null;
    event_kind: "customer_message" | "agent_reply" | "system_log" | "internal_event";
    direction: "inbound" | "outbound" | "system";
    channel: string;
    sender_type: string;
    content: string;
    sentiment: {
      label: "positive" | "neutral" | "negative";
      score: number;
    };
    conversation: {
      id: string;
      status: string;
    };
    customer: {
      id: string;
      name: string | null;
      email: string | null;
    };
  }>;
};

type DashboardAnalytics = {
  period_hours: number;
  bucket_hours: number;
  generated_at: string;
  series: Array<{
    bucket: string | null;
    messages: number;
    escalations: number;
  }>;
};

type AssignedTicketsResponse = {
  count: number;
  items: Array<{
    id: string;
    title: string;
    description: string | null;
    status: string;
    priority: string;
    created_at: string | null;
    resolved_at: string | null;
    conversation: {
      id: string | null;
      status: string | null;
      channel: string | null;
    };
    customer: {
      id: string | null;
      name: string | null;
      email: string | null;
      phone_number: string | null;
    };
    latest_message: {
      content: string | null;
      sender_type: string | null;
      created_at: string | null;
    };
  }>;
};

export default function AdminDashboardPage() {
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<"dashboard" | "tickets">("dashboard");
  const [hours, setHours] = useState(24);
  const [activityLimit, setActivityLimit] = useState(80);
  const [activityChannel, setActivityChannel] = useState("all");
  const [activitySender, setActivitySender] = useState("all");
  const [activitySentiment, setActivitySentiment] = useState("all");

  const [data, setData] = useState<DashboardResponse | null>(null);
  const [analytics, setAnalytics] = useState<DashboardAnalytics | null>(null);
  const [activity, setActivity] = useState<DashboardActivity | null>(null);
  const [tickets, setTickets] = useState<AssignedTicketsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [replyingTicketId, setReplyingTicketId] = useState<string | null>(null);

  const loadDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const credentials = getAdminCredentials();
      if (!credentials) {
        router.replace("/admin/login");
        return;
      }

      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

      const commonHeaders = {
        "X-Admin-User": credentials.username,
        "X-Admin-Password": credentials.password,
      };

      const activityParams = new URLSearchParams({
        hours: String(hours),
        limit: String(activityLimit),
      });
      if (activityChannel !== "all") {
        activityParams.set("channel", activityChannel);
      }
      if (activitySender !== "all") {
        activityParams.set("sender_type", activitySender);
      }
      if (activitySentiment !== "all") {
        activityParams.set("sentiment", activitySentiment);
      }

      const [dashboardRes, analyticsRes, activityRes, ticketsRes] = await Promise.all([
        fetch(`${apiBase}/api/admin/dashboard?hours=${hours}`, {
          cache: "no-store",
          headers: commonHeaders,
        }),
        fetch(`${apiBase}/api/admin/dashboard/analytics?hours=${hours}&bucket_hours=1`, {
          cache: "no-store",
          headers: commonHeaders,
        }),
        fetch(`${apiBase}/api/admin/dashboard/activity?${activityParams.toString()}`, {
          cache: "no-store",
          headers: commonHeaders,
        }),
        fetch(`${apiBase}/api/admin/tickets?status=open&limit=100`, {
          cache: "no-store",
          headers: commonHeaders,
        }),
      ]);

      if (!dashboardRes.ok || !analyticsRes.ok || !activityRes.ok || !ticketsRes.ok) {
        if (
          dashboardRes.status === 401 ||
          analyticsRes.status === 401 ||
          activityRes.status === 401 ||
          ticketsRes.status === 401
        ) {
          clearAdminCredentials();
          router.replace("/admin/login?reason=expired");
          return;
        }
        throw new Error("Unauthorized or unable to load dashboard data");
      }

      const dashboardJson = (await dashboardRes.json()) as DashboardResponse;
      const analyticsJson = (await analyticsRes.json()) as DashboardAnalytics;
      const activityJson = (await activityRes.json()) as DashboardActivity;
      const ticketsJson = (await ticketsRes.json()) as AssignedTicketsResponse;

      setData(dashboardJson);
      setAnalytics(analyticsJson);
      setActivity(activityJson);
      setTickets(ticketsJson);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  };

  const submitTicketReply = async (ticketId: string) => {
    const replyText = (replyDrafts[ticketId] || "").trim();
    if (!replyText) {
      setError("Reply text is required");
      return;
    }

    try {
      setReplyingTicketId(ticketId);
      setError(null);

      const credentials = getAdminCredentials();
      if (!credentials) {
        router.replace("/admin/login");
        return;
      }

      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${apiBase}/api/admin/tickets/${ticketId}/reply`, {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-User": credentials.username,
          "X-Admin-Password": credentials.password,
        },
        body: JSON.stringify({ response_text: replyText, mark_resolved: false }),
      });

      if (!response.ok) {
        throw new Error("Failed to send ticket reply");
      }

      setReplyDrafts((current) => ({ ...current, [ticketId]: "" }));
      await loadDashboard();
      setActiveTab("tickets");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send ticket reply");
    } finally {
      setReplyingTicketId(null);
    }
  };

  useEffect(() => {
    loadDashboard();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hours, activityLimit, activityChannel, activitySender, activitySentiment]);

  const sentimentSourceText = useMemo(() => {
    if (!data?.sentiments?.source) {
      return "Not available";
    }
    return data.sentiments.source === "final_outcome"
      ? "Final Outcome Markers"
      : "Heuristic Message Analysis";
  }, [data]);

  const averageSentimentDisplay = useMemo(() => {
    if (!data) {
      return "-";
    }

    const score = data.sentiments.avg_score;
    const wholeNumberDelta = Math.round(Math.abs(score) * 100);

    if (wholeNumberDelta === 0) {
      return "Neutral 0";
    }

    return score > 0 ? `Up ${wholeNumberDelta}` : `Down ${wholeNumberDelta}`;
  }, [data]);

  return (
    <main className="min-h-screen bg-[#0b1220] text-slate-100">
      <div className="border-b border-slate-800 bg-slate-950">
        <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 md:px-10 md:py-8">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">Softech Global Services</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight text-slate-100 md:text-3xl">Support Intelligence Dashboard</h1>
              <p className="mt-2 max-w-3xl text-sm text-slate-300 md:text-base">
                Executive view of support operations, customer outcomes, escalation risk, and active tickets.
              </p>
            </div>
            <div className="flex w-full flex-col gap-3 md:w-auto md:items-end">
              <div className="grid w-full grid-cols-2 gap-2 md:w-auto md:grid-cols-2">
                <Link
                  href="/"
                  className="inline-flex items-center justify-center rounded-lg border border-cyan-700 bg-cyan-900/40 px-3 py-2 text-sm font-semibold text-cyan-200 transition hover:bg-cyan-800/50"
                >
                  Back to Web Intake
                </Link>
                <button
                  type="button"
                  onClick={() => {
                    clearAdminCredentials();
                    router.push("/admin/login");
                  }}
                  className="inline-flex items-center justify-center rounded-lg border border-rose-700 bg-rose-900/40 px-3 py-2 text-sm font-semibold text-rose-200 transition hover:bg-rose-800/50"
                >
                  Logout
                </button>
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-300">
                Last refresh: {data ? new Date(data.generated_at).toLocaleString() : "-"}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl space-y-6 px-6 py-6 md:px-10 md:py-8">
        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm md:p-5">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
            <FilterSelect value={hours} onChange={(v) => setHours(Number(v))}>
              <option value={6}>Last 6 hours</option>
              <option value={24}>Last 24 hours</option>
              <option value={72}>Last 72 hours</option>
              <option value={168}>Last 7 days</option>
            </FilterSelect>

            <FilterSelect value={activityChannel} onChange={setActivityChannel}>
              <option value="all">All Channels</option>
              <option value="web">Web</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="email">Email</option>
            </FilterSelect>

            <FilterSelect value={activitySender} onChange={setActivitySender}>
              <option value="all">All Senders</option>
              <option value="user">User</option>
              <option value="customer">Customer</option>
              <option value="agent">Agent</option>
              <option value="system">System</option>
            </FilterSelect>

            <FilterSelect value={activitySentiment} onChange={setActivitySentiment}>
              <option value="all">All Sentiments</option>
              <option value="negative">Negative</option>
              <option value="neutral">Neutral</option>
              <option value="positive">Positive</option>
            </FilterSelect>

            <FilterSelect value={activityLimit} onChange={(v) => setActivityLimit(Number(v))}>
              <option value={40}>40 Events</option>
              <option value={80}>80 Events</option>
              <option value={120}>120 Events</option>
              <option value={200}>200 Events</option>
            </FilterSelect>

            <button
              onClick={loadDashboard}
              className="rounded-lg bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-500"
            >
              Refresh Data
            </button>
          </div>
        </section>

        <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("dashboard")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeTab === "dashboard"
                  ? "bg-cyan-600 text-slate-950"
                  : "border border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-500"
              }`}
            >
              Dashboard
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("tickets")}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                activeTab === "tickets"
                  ? "bg-cyan-600 text-slate-950"
                  : "border border-slate-700 bg-slate-900 text-slate-200 hover:border-slate-500"
              }`}
            >
              Assigned Tickets {tickets ? `(${tickets.count})` : ""}
            </button>
          </div>
        </header>

        {loading && <p className="text-sm text-slate-300">Loading dashboard...</p>}
        {error && <p className="rounded-lg border border-rose-700 bg-rose-900/40 px-4 py-3 text-sm text-rose-200">{error}</p>}

        {activeTab === "dashboard" && data && (
          <>
            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-6">
              <MetricCard label="Total Tickets" value={data.kpis.tickets_total} tone="blue" />
              <MetricCard label="Open Tickets" value={data.kpis.tickets_open} tone="amber" />
              <MetricCard label="Total Messages" value={data.kpis.messages_total} tone="slate" />
              <MetricCard label="Escalated Conversations" value={data.kpis.conversations_escalated} tone="rose" />
              <MetricCard label="Messages (Window)" value={data.kpis.messages_24h} tone="blue" />
              <MetricCard label="Escalation Rate" value={`${data.kpis.escalation_rate}%`} tone="amber" />
            </section>

            <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm xl:col-span-2">
                <h2 className="text-lg font-semibold text-slate-100">Traffic and Escalation Trend</h2>
                <p className="mt-1 text-sm text-slate-300">
                  Timeseries for the selected window ({analytics?.period_hours ?? hours}h)
                </p>
                {analytics ? (
                  <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
                    <MiniBarChart title="Messages per Hour" values={analytics.series.map((point) => point.messages)} />
                    <MiniBarChart title="Escalations per Hour" values={analytics.series.map((point) => point.escalations)} />
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-slate-400">Analytics loading...</p>
                )}
              </div>

              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm">
                <h2 className="text-lg font-semibold text-slate-100">Sentiment Outcome</h2>
                <p className="mt-1 text-sm text-slate-300">Source: {sentimentSourceText}</p>

                <div className="mt-4 space-y-3">
                  <MetricRow label="Average Score" value={averageSentimentDisplay} />
                  <MetricRow label="Positive" value={String(data.sentiments.positive)} />
                  <MetricRow label="Neutral" value={String(data.sentiments.neutral)} />
                  <MetricRow label="Negative" value={String(data.sentiments.negative)} />
                </div>
              </div>
            </section>

            <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm xl:col-span-2">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <h2 className="text-lg font-semibold text-slate-100">Conversation Activity</h2>
                  <p className="text-xs text-slate-400">{activity?.count || 0} events</p>
                </div>
                {!activity || activity.items.length === 0 ? (
                  <p className="text-sm text-slate-400">No activity found for selected filters.</p>
                ) : (
                  <div className="max-h-[34rem] space-y-3 overflow-y-auto pr-1">
                    {activity.items.map((item) => (
                      <article key={item.id} className="rounded-xl border border-slate-700 bg-slate-900 p-3">
                        <div className="mb-2 flex flex-wrap gap-2">
                          <Tag text={item.event_kind.replace("_", " ")} tone="blue" />
                          <Tag
                            text={item.direction}
                            tone={item.direction === "inbound" ? "emerald" : item.direction === "outbound" ? "indigo" : "slate"}
                          />
                          <Tag text={item.channel} tone="slate" />
                          <Tag
                            text={`sentiment ${item.sentiment.label}`}
                            tone={item.sentiment.label === "negative" ? "rose" : item.sentiment.label === "positive" ? "emerald" : "slate"}
                          />
                        </div>
                        <p className="text-sm text-slate-100">{item.content}</p>
                        <div className="mt-2 grid grid-cols-1 gap-2 text-xs text-slate-400 md:grid-cols-3">
                          <span>Time: {item.timestamp ? new Date(item.timestamp).toLocaleString() : "-"}</span>
                          <span>Conversation: {item.conversation.id} ({item.conversation.status})</span>
                          <span>Customer: {item.customer.name || item.customer.email || "Unknown"}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-6">
                <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-100">Channel Health</h2>
                  <div className="mt-3 space-y-2">
                    {data.channels.map((channel) => (
                      <div key={channel.channel} className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium capitalize text-slate-100">{channel.channel}</span>
                          <Tag
                            text={channel.status}
                            tone={
                              channel.status === "healthy"
                                ? "emerald"
                                : channel.status === "degraded"
                                  ? "amber"
                                  : "rose"
                            }
                          />
                        </div>
                        <p className="mt-1 text-xs text-slate-400">
                          Inbound {channel.inbound} | Outbound {channel.outbound} | Total {channel.total}
                        </p>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm">
                  <h2 className="text-lg font-semibold text-slate-100">Negative Watchlist</h2>
                  {data.sentiments.recent_negative_examples.length === 0 ? (
                    <p className="mt-3 text-sm text-slate-400">No negative outcomes in selected window.</p>
                  ) : (
                    <div className="mt-3 space-y-2">
                      {data.sentiments.recent_negative_examples.slice(0, 5).map((item, idx) => (
                        <article key={`${item.conversation_id}-${idx}`} className="rounded-lg border border-rose-700 bg-rose-900/35 p-2.5">
                          <p className="text-xs text-rose-200">
                            {item.channel} | score {item.score.toFixed(3)}
                          </p>
                          <p className="mt-1 line-clamp-3 text-sm text-slate-100">{item.content}</p>
                        </article>
                      ))}
                    </div>
                  )}
                </section>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-100">Status Logs</h2>
              <div className="mt-3 max-h-80 overflow-y-auto rounded-xl border border-slate-700">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-900">
                    <tr className="text-left text-slate-300">
                      <th className="px-3 py-2">Time</th>
                      <th className="px-3 py-2">Level</th>
                      <th className="px-3 py-2">Source</th>
                      <th className="px-3 py-2">Event</th>
                      <th className="px-3 py-2">Channel</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_status_logs.map((log, idx) => (
                      <tr key={`${log.source}-${idx}`} className="border-t border-slate-800 text-slate-200">
                        <td className="px-3 py-2">{log.timestamp ? new Date(log.timestamp).toLocaleString() : "-"}</td>
                        <td className="px-3 py-2 uppercase">{log.level}</td>
                        <td className="px-3 py-2">{log.source}</td>
                        <td className="px-3 py-2">{log.message}</td>
                        <td className="px-3 py-2">{log.metadata.channel || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}

        {activeTab === "tickets" && (
          <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">Assigned Tickets</h2>
                <p className="text-sm text-slate-300">Reply from dashboard. Messages are saved and dispatched to customer channel.</p>
              </div>
              <button
                type="button"
                onClick={loadDashboard}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-500"
              >
                Refresh Tickets
              </button>
            </div>

            {!tickets || tickets.items.length === 0 ? (
              <p className="text-sm text-slate-400">No open tickets in the current filter.</p>
            ) : (
              <div className="space-y-3">
                {tickets.items.map((ticket) => (
                  <article key={ticket.id} className="rounded-xl border border-slate-700 bg-slate-900 p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-300">
                      <Tag text={ticket.conversation.channel || "web"} tone="slate" />
                      <Tag text={ticket.priority} tone="amber" />
                      <Tag text={ticket.status} tone="blue" />
                      <span>{ticket.customer.name || ticket.customer.email || "Unknown customer"}</span>
                      <span>{ticket.created_at ? new Date(ticket.created_at).toLocaleString() : "-"}</span>
                    </div>

                    <h3 className="text-base font-semibold text-slate-100">{ticket.title}</h3>
                    {ticket.description && <p className="mt-1 text-sm text-slate-300">{ticket.description}</p>}

                    <div className="mt-3 rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm text-slate-200">
                      <p className="mb-1 text-xs uppercase tracking-wide text-slate-400">Latest message</p>
                      <p>{ticket.latest_message.content || "No messages yet."}</p>
                    </div>

                    <textarea
                      className="mt-3 min-h-28 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500"
                      placeholder="Write the reply that should be sent back to the customer..."
                      value={replyDrafts[ticket.id] || ""}
                      onChange={(event) =>
                        setReplyDrafts((current) => ({ ...current, [ticket.id]: event.target.value }))
                      }
                    />

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                      <p className="text-xs text-slate-400">
                        Channel: {ticket.conversation.channel || "web"} | Conversation: {ticket.conversation.id || "-"}
                      </p>
                      <button
                        type="button"
                        onClick={() => submitTicketReply(ticket.id)}
                        disabled={replyingTicketId === ticket.id}
                        className="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-400 disabled:bg-indigo-900 disabled:text-slate-400"
                      >
                        {replyingTicketId === ticket.id ? "Sending..." : "Send Reply"}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </main>
  );
}

function FilterSelect({
  value,
  onChange,
  children,
}: {
  value: string | number;
  onChange: (value: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      {children}
    </select>
  );
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone: "slate" | "blue" | "amber" | "emerald" | "rose";
}) {
  const toneMap: Record<string, string> = {
    slate: "border-slate-700",
    blue: "border-cyan-700",
    amber: "border-amber-700",
    emerald: "border-emerald-700",
    rose: "border-rose-700",
  };

  return (
    <article className={`rounded-2xl border bg-slate-900/80 p-4 shadow-sm ${toneMap[tone] || toneMap.slate}`}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-300">{label}</p>
      <p className="mt-2 text-2xl font-bold text-slate-100">{value}</p>
    </article>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-950 px-3 py-2">
      <span className="text-sm text-slate-300">{label}</span>
      <span className="text-sm font-semibold text-slate-100">{value}</span>
    </div>
  );
}

function Tag({ text, tone }: { text: string; tone: "slate" | "blue" | "amber" | "emerald" | "indigo" | "rose" }) {
  const classes: Record<string, string> = {
    slate: "border-slate-700 bg-slate-900 text-slate-200",
    blue: "border-cyan-700 bg-cyan-900/40 text-cyan-200",
    amber: "border-amber-700 bg-amber-900/40 text-amber-200",
    emerald: "border-emerald-700 bg-emerald-900/40 text-emerald-200",
    indigo: "border-indigo-700 bg-indigo-900/40 text-indigo-200",
    rose: "border-rose-700 bg-rose-900/40 text-rose-200",
  };

  return <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium ${classes[tone] || classes.slate}`}>{text}</span>;
}

function MiniBarChart({ title, values }: { title: string; values: number[] }) {
  const max = Math.max(...values, 1);

  return (
    <div className="rounded-xl border border-slate-700 bg-slate-950/80 p-3">
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      <div className="mt-3 flex h-28 items-end gap-1">
        {values.length === 0 ? (
          <div className="text-xs text-slate-400">No data in selected period</div>
        ) : (
          values.map((value, idx) => (
            <div
              key={`${title}-${idx}`}
              className="flex-1 rounded-t bg-blue-500/80"
              style={{ height: `${Math.max(8, Math.round((value / max) * 100))}%` }}
              title={`${value}`}
            />
          ))
        )}
      </div>
    </div>
  );
}
