import {
  Building2,
  ChevronsLeft,
  ClipboardList,
  Cpu,
  FolderKanban,
  Inbox,
  LayoutDashboard,
  Menu,
  PanelRightOpen,
  Search,
  Sparkles,
  Zap,
} from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import type { ComponentType } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";
import { ChatPanel } from "./chat";
import { API_BASE } from "../lib/api";
import { cn } from "../lib/cn";
import { CommandPalette, IconButton, Sheet, ThemeToggle, Tooltip, useCommandPaletteHotkey, type CommandGroup } from "./ui";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  end?: boolean;
}

interface NavSection {
  heading: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  { heading: "Overview", items: [{ to: "/", label: "Command Center", icon: LayoutDashboard, end: true }] },
  {
    heading: "Engineering",
    items: [
      { to: "/feasibility", label: "Feasibility", icon: Zap },
      { to: "/procurement", label: "Procurement", icon: Inbox },
      { to: "/components", label: "Components", icon: Cpu },
    ],
  },
  {
    heading: "Operations",
    items: [
      { to: "/projects", label: "Projects", icon: FolderKanban },
      { to: "/vendors", label: "Vendors", icon: Building2 },
      { to: "/purchase-orders", label: "Purchase Orders", icon: ClipboardList },
    ],
  },
];

const FLAT_NAV = NAV_SECTIONS.flatMap((s) => s.items);
const SIDEBAR_COLLAPSE_KEY = "sitepilot-sidebar-collapsed";
const CHAT_COLLAPSE_KEY = "sitepilot-chat-collapsed";

function SidebarNavContent({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  return (
    <nav className="flex-1 space-y-5 overflow-y-auto px-2.5 py-4">
      {NAV_SECTIONS.map((section) => (
        <div key={section.heading}>
          {!collapsed && (
            <p className="px-2.5 pb-1.5 text-[11px] font-medium uppercase tracking-wide text-subtle">{section.heading}</p>
          )}
          <div className="space-y-0.5">
            {section.items.map((item) => {
              const link = (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className="group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium text-muted transition-colors duration-[120ms] ease-out hover:text-text"
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <motion.span
                          layoutId="sidebar-active-indicator"
                          className="absolute inset-0 rounded-md bg-accent/12"
                          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                        />
                      )}
                      {isActive && <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent" aria-hidden="true" />}
                      <item.icon className={cn("relative size-4.5 shrink-0", isActive && "text-accent")} />
                      {!collapsed && <span className={cn("relative truncate", isActive && "text-text")}>{item.label}</span>}
                    </>
                  )}
                </NavLink>
              );

              return collapsed ? (
                <Tooltip key={item.to} content={item.label} side="right">
                  {link}
                </Tooltip>
              ) : (
                link
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function useConnectionStatus(): "connecting" | "online" | "offline" {
  const [status, setStatus] = useState<"connecting" | "online" | "offline">("connecting");

  useEffect(() => {
    const source = new EventSource(`${API_BASE}/events`);
    source.onopen = () => setStatus("online");
    source.onerror = () => setStatus("offline");
    return () => source.close();
  }, []);

  return status;
}

function ConnectionIndicator() {
  const status = useConnectionStatus();
  const label =
    status === "online" ? "Live — connected to the activity feed" : status === "offline" ? "Disconnected — retrying…" : "Connecting…";
  const dotClass = status === "online" ? "bg-success" : status === "offline" ? "bg-danger" : "bg-subtle";

  return (
    <Tooltip content={label} side="bottom">
      <span className="inline-flex items-center gap-1.5 rounded-full px-2 py-1" aria-label={label}>
        <span className={cn("size-1.5 rounded-full", dotClass, status === "online" && "motion-safe:animate-pulse")} />
      </span>
    </Tooltip>
  );
}

function useBreadcrumb(): string[] {
  const location = useLocation();
  const params = useParams();

  return useMemo(() => {
    const path = location.pathname;
    if (path === "/") return ["Command Center"];

    const match = FLAT_NAV.find((item) => item.to !== "/" && path.startsWith(item.to));
    if (!match) return ["SitePilot"];

    const crumbs = [match.label];
    if (path.startsWith("/projects/") && params.id) crumbs.push(`Project #${params.id}`);
    return crumbs;
  }, [location.pathname, params.id]);
}

export default function Layout() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [chatSheetOpen, setChatSheetOpen] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(() => {
    try {
      return localStorage.getItem(CHAT_COLLAPSE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const navigate = useNavigate();
  const breadcrumb = useBreadcrumb();
  const reduceMotion = useReducedMotion();

  useCommandPaletteHotkey(() => setPaletteOpen((v) => !v));

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  }

  function toggleChatCollapsed() {
    setChatCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(CHAT_COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // ignore
      }
      return next;
    });
  }

  const commandGroups: CommandGroup[] = [
    {
      heading: "Go to",
      items: FLAT_NAV.map((item) => ({
        id: item.to,
        label: item.label,
        icon: <item.icon />,
        onSelect: () => navigate(item.to),
      })),
    },
  ];

  return (
    <div className="flex h-screen overflow-hidden bg-bg text-text">
      {/* Desktop sidebar */}
      <motion.aside
        animate={{ width: collapsed ? 64 : 232 }}
        transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.16, 1, 0.3, 1] }}
        className="hidden shrink-0 flex-col border-r border-border bg-bg-elevated md:flex"
      >
        <div className="flex items-center gap-2.5 border-b border-border px-3.5 py-4">
          <img src="/favicon.svg" alt="" className="size-8 shrink-0 rounded-lg" />
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold leading-tight text-text">SitePilot</p>
              <p className="truncate text-[11px] text-subtle">Solar ops co-pilot</p>
            </div>
          )}
        </div>

        <SidebarNavContent collapsed={collapsed} />

        <div className="border-t border-border p-2">
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted transition-colors duration-[120ms] hover:bg-surface-hover hover:text-text"
          >
            <ChevronsLeft className={cn("size-4.5 shrink-0 transition-transform duration-[200ms]", collapsed && "rotate-180")} />
            {!collapsed && "Collapse"}
          </button>
        </div>
      </motion.aside>

      {/* Mobile nav drawer */}
      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen} side="left" title="SitePilot">
        <SidebarNavContent collapsed={false} onNavigate={() => setMobileNavOpen(false)} />
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-bg-elevated px-4">
          <IconButton
            icon={<Menu />}
            aria-label="Open navigation"
            className="md:hidden"
            onClick={() => setMobileNavOpen(true)}
          />

          <nav aria-label="Breadcrumb" className="min-w-0 flex-1">
            <ol className="flex items-center gap-1.5 truncate text-sm">
              {breadcrumb.map((crumb, i) => (
                <li key={crumb} className="flex items-center gap-1.5 truncate">
                  {i > 0 && <span className="text-subtle">/</span>}
                  <span className={cn("truncate", i === breadcrumb.length - 1 ? "font-medium text-text" : "text-muted")}>{crumb}</span>
                </li>
              ))}
            </ol>
          </nav>

          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="hidden items-center gap-2 rounded-md border border-border bg-bg-subtle px-2.5 py-1.5 text-xs text-muted transition-colors duration-[120ms] hover:text-text sm:inline-flex"
          >
            <Search className="size-3.5" aria-hidden="true" />
            Search
            <kbd className="ml-1 rounded border border-border px-1 py-0.5 font-sans text-[10px]">⌘K</kbd>
          </button>
          <IconButton icon={<Search />} aria-label="Search" className="sm:hidden" onClick={() => setPaletteOpen(true)} />

          <ConnectionIndicator />
          <ThemeToggle />
        </header>

        <div className="flex min-h-0 flex-1">
          <main className="min-w-0 flex-1 overflow-y-auto p-6 lg:p-8">
            <Outlet />
          </main>

          {/* Docked right rail at >=1280px (xl) — below that the chat lives in the bottom sheet.
              Collapsible to a thin strip; state persists in localStorage. */}
          <motion.aside
            animate={{ width: chatCollapsed ? 44 : 380 }}
            transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="hidden min-h-0 shrink-0 flex-col overflow-hidden border-l border-border bg-bg-subtle xl:flex"
          >
            {chatCollapsed ? (
              <button
                type="button"
                onClick={toggleChatCollapsed}
                aria-label="Expand Fieldbot"
                className="flex h-full w-11 flex-col items-center gap-3 py-4 text-muted transition-colors duration-[120ms] hover:bg-surface-hover hover:text-text"
              >
                <PanelRightOpen className="size-4.5 shrink-0" />
                <span className="text-xs font-medium tracking-wide [writing-mode:vertical-rl]">Fieldbot</span>
              </button>
            ) : (
              <ChatPanel onCollapse={toggleChatCollapsed} />
            )}
          </motion.aside>
        </div>
      </div>

      {/* Floating toggle + bottom sheet host for the chat panel below the xl breakpoint. */}
      <IconButton
        icon={<Sparkles />}
        aria-label="Open Fieldbot chat"
        onClick={() => setChatSheetOpen(true)}
        className="fixed bottom-5 right-5 z-40 size-12 rounded-full border border-border bg-accent text-accent-fg shadow-lg hover:bg-accent-hover xl:hidden [&_svg]:size-5"
      />
      <div className="xl:hidden">
        {/* Explicit height (rather than Sheet's default max-h cap alone) so ChatPanel's internal
            `h-full` flex layout — and MessageList's own scroll region — has a real size to resolve
            against instead of collapsing to its content's natural height. */}
        <Sheet open={chatSheetOpen} onOpenChange={setChatSheetOpen} side="bottom" className="h-[85vh]">
          <ChatPanel onRequestClose={() => setChatSheetOpen(false)} />
        </Sheet>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} groups={commandGroups} />
    </div>
  );
}
