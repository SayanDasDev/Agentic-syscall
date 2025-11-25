"use client";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
} from "@/components/ui/chart";
import {
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  BarChart,
  Bar,
  AreaChart,
  Area,
} from "recharts";

type Usage = {
  ru_utime: { tv_sec: number; tv_usec: number };
  ru_stime: { tv_sec: number; tv_usec: number };
  ru_maxrss: number;
  ru_minflt: number;
  ru_majflt: number;
  ts: number;
};

export default function Home() {
  const [history, setHistory] = useState<Usage[]>([]);
  const [status, setStatus] = useState("connecting");
  const [agentState, setAgentState] = useState("idle");
  const [text, setText] = useState("");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    wsRef.current = ws;
    ws.onopen = () => setStatus("connected");
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as Usage;
        setHistory((prev) => [...prev.slice(-59), data]);
        if (agentState === "thinking") setAgentState("streaming");
      } catch {}
    };
    ws.onerror = () => setStatus("error");
    ws.onclose = () => setStatus("closed");
    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [agentState]);

  const sendText = () => {
    if (!wsRef.current || status !== "connected") return;
    const t = text.trim();
    if (!t) return;
    setAgentState("thinking");
    wsRef.current.send(t);
  };

  const stopStreaming = () => {
    if (!wsRef.current || status !== "connected") return;
    setAgentState("thinking");
    wsRef.current.send("stop");
    setTimeout(() => setAgentState("stopped"), 400);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex min-h-screen w-full max-w-screen flex-col items-center justify-between py-16 px-6 bg-white dark:bg-black sm:items-start">

        <div className="mt-6 w-full space-y-6">
          <div className="flex items-center justify-between">
            <div className="text-sm text-zinc-600 dark:text-zinc-400">WS: {status}</div>
            <div className="flex items-center gap-2">
              {agentState === "thinking" && (
                <Badge variant="secondary"><Loader2 className="animate-spin" /> thinking</Badge>
              )}
              {agentState === "streaming" && (
                <Badge>streaming</Badge>
              )}
              {agentState === "stopped" && (
                <Badge variant="outline">stopped</Badge>
              )}
              {agentState === "idle" && (
                <Badge variant="outline">idle</Badge>
              )}
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Control</CardTitle>
              <CardDescription>Describe cadence, e.g. {`"every 5 seconds for 10 samples"`}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Type a command"
                />
                <Button onClick={sendText}>Send</Button>
                <Button variant="secondary" onClick={stopStreaming}>Stop</Button>
              </div>
            </CardContent>
          </Card>

{/* Stats */}
          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle>Current User CPU</CardTitle>
                <CardDescription>seconds</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {history.length
                    ? (history[history.length - 1].ru_utime.tv_sec + history[history.length - 1].ru_utime.tv_usec / 1_000_000).toFixed(3)
                    : "-"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Current System CPU</CardTitle>
                <CardDescription>seconds</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {history.length
                    ? (history[history.length - 1].ru_stime.tv_sec + history[history.length - 1].ru_stime.tv_usec / 1_000_000).toFixed(3)
                    : "-"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Current RSS</CardTitle>
                <CardDescription>KB</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {history.length ? history[history.length - 1].ru_maxrss.toLocaleString() : "-"}
                </div>
              </CardContent>
            </Card>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            
            <Card>
              <CardHeader>
                <CardTitle>CPU Time</CardTitle>
                <CardDescription>User/System seconds over time</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer
                  config={{
                    user: { label: "User", color: "hsl(220 90% 56%)" },
                    system: { label: "System", color: "hsl(10 85% 52%)" },
                  }}
                >
                  <LineChart data={history.map((h) => ({
                    ts: h.ts,
                    user: h.ru_utime.tv_sec + h.ru_utime.tv_usec / 1_000_000,
                    system: h.ru_stime.tv_sec + h.ru_stime.tv_usec / 1_000_000,
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="ts"
                      tickFormatter={(t) => new Date(t * 1000).toLocaleTimeString()}
                    />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Line type="monotone" dataKey="user" stroke="var(--color-user)" dot={false} />
                    <Line type="monotone" dataKey="system" stroke="var(--color-system)" dot={false} />
                    <ChartLegend content={<ChartLegendContent />} />
                  </LineChart>
                </ChartContainer>
              </CardContent>
            </Card>

            {/* CPU Time Card */}
            <Card>
              <CardHeader>
                <CardTitle>Memory RSS</CardTitle>
                <CardDescription>Max RSS (KB) over time</CardDescription>
              </CardHeader>
              <CardContent>
                <ChartContainer
                  config={{ rss: { label: "Max RSS", color: "hsl(140 70% 40%)" } }}
                >
                  <AreaChart data={history.map((h) => ({ ts: h.ts, rss: h.ru_maxrss }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="ts"
                      tickFormatter={(t) => new Date(t * 1000).toLocaleTimeString()}
                    />
                    <YAxis />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Area type="monotone" dataKey="rss" stroke="var(--color-rss)" fill="var(--color-rss)" />
                  </AreaChart>
                </ChartContainer>
              </CardContent>
            </Card>
          </div>

          {/* Page Fault Card */}
          <Card>
            <CardHeader>
              <CardTitle>Page Faults</CardTitle>
              <CardDescription>Minor vs Major faults</CardDescription>
            </CardHeader>
            <CardContent>
              <ChartContainer
                config={{
                  minflt: { label: "Minor", color: "hsl(40 90% 50%)" },
                  majflt: { label: "Major", color: "hsl(300 70% 55%)" },
                }}
              >
                <BarChart data={history.map((h) => ({ ts: h.ts, minflt: h.ru_minflt, majflt: h.ru_majflt }))}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="ts"
                    tickFormatter={(t) => new Date(t * 1000).toLocaleTimeString()}
                  />
                  <YAxis />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="minflt" fill="var(--color-minflt)" />
                  <Bar dataKey="majflt" fill="var(--color-majflt)" />
                  <ChartLegend content={<ChartLegendContent />} />
                </BarChart>
              </ChartContainer>
            </CardContent>
          </Card>

          
        </div>
      </main>
    </div>
  );
}
