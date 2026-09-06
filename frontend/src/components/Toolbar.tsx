"use client";

import {
  Bell,
  Home,
  LayoutDashboard,
  Users,
  Wrench,
  ShieldCheck,
  CheckCircle,
  AlertTriangle,
  ListTodo,
  BookOpen,
  Puzzle,
  Mail,
  Briefcase,
  Inbox,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion, type Transition, type Variants } from "motion/react";
import * as React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

interface ToolbarItem {
  id: string;
  to: string;
  title: string;
  icon: LucideIcon;
}

interface ToolbarProps {
  items?: ToolbarItem[];
  className?: string;
}

const DEFAULT_TOOLBAR_ITEMS: ToolbarItem[] = [
  { id: "home", to: "/", title: "Home", icon: Home },
  { id: "office", to: "/office", title: "Office", icon: Briefcase },
  { id: "dashboard", to: "/dashboard", title: "Dashboard", icon: LayoutDashboard },
  { id: "inbox", to: "/ceo/inbox", title: "Inbox", icon: Inbox },
  { id: "ceo", to: "/ceo", title: "CEO", icon: Users },
  { id: "agents", to: "/agents", title: "Agents", icon: Users },
  { id: "tools", to: "/tools", title: "Tools", icon: Wrench },
  { id: "permissions", to: "/permissions", title: "Permissions", icon: ShieldCheck },
  { id: "approvals", to: "/approvals", title: "Approvals", icon: CheckCircle },
  { id: "risk", to: "/risk-settings", title: "Risk", icon: AlertTriangle },
  { id: "tasks", to: "/tasks", title: "Tasks", icon: ListTodo },
  { id: "knowledge", to: "/knowledge", title: "Knowledge", icon: BookOpen },
  { id: "integrations", to: "/integrations", title: "Integrations", icon: Puzzle },
  { id: "emails", to: "/emails", title: "Emails", icon: Mail },
];

const buttonVariants: Variants = {
  initial: {
    gap: 0,
    paddingLeft: ".5rem",
    paddingRight: ".5rem",
  },
  animate: (isSelected: boolean) => ({
    gap: isSelected ? ".5rem" : 0,
    paddingLeft: isSelected ? "1rem" : ".5rem",
    paddingRight: isSelected ? "1rem" : ".5rem",
  }),
};

const spanVariants: Variants = {
  initial: { width: 0, opacity: 0 },
  animate: { width: "auto", opacity: 1 },
  exit: { width: 0, opacity: 0 },
};

const notificationVariants: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: -10 },
  exit: { opacity: 0, y: -20 },
};

const lineVariants: Variants = {
  initial: { scaleX: 0, x: "-50%" },
  animate: {
    scaleX: 1,
    x: "0%",
    transition: { duration: 0.2, ease: "easeOut" },
  },
  exit: {
    scaleX: 0,
    x: "50%",
    transition: { duration: 0.2, ease: "easeIn" },
  },
};

const transition: Transition = { type: "spring", bounce: 0, duration: 0.4 };

export function Toolbar({
  items = DEFAULT_TOOLBAR_ITEMS,
  className,
  connected,
  unreadNotifications,
  pendingApprovals,
}: ToolbarProps & { connected?: boolean; unreadNotifications?: number; pendingApprovals?: number }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [selected, setSelected] = React.useState<string | null>(null);
  const [activeNotification, setActiveNotification] = React.useState<string | null>(null);

  // Sync selected with route on mount / route change
  React.useEffect(() => {
    const match = items.find((item) => {
      if (item.to === "/") return location.pathname === "/";
      return location.pathname === item.to || location.pathname.startsWith(item.to + "/");
    });
    if (match) setSelected(match.id);
  }, [location.pathname, items]);

  const handleItemClick = (item: ToolbarItem) => {
    setSelected(item.id);
    setActiveNotification(item.id);
    setTimeout(() => setActiveNotification(null), 1500);
    navigate(item.to);
  };

  return (
    <div className="space-y-2">
      <div
        className={cn(
          "fixed bottom-6 left-1/2 -translate-x-1/2 z-50",
          "flex items-center gap-3 p-2",
          "bg-background",
          "rounded-xl border shadow-lg",
          "transition-all duration-200",
          className
        )}
      >
        <AnimatePresence>
          {activeNotification && (
            <motion.div
              animate="animate"
              className="absolute -top-8 left-1/2 z-50 -translate-x-1/2 transform"
              exit="exit"
              initial="initial"
              transition={{ duration: 0.3 }}
              variants={notificationVariants}
            >
              <div className="rounded-full bg-primary px-3 py-1 text-primary-foreground text-xs">
                {items.find((item) => item.id === activeNotification)?.title}{" "}
                clicked!
              </div>
              <motion.div
                animate="animate"
                className="absolute -bottom-1 left-1/2 h-[2px] w-full origin-left bg-primary"
                exit="exit"
                initial="initial"
                variants={lineVariants}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center gap-2">
          {items.map((item) => (
            <motion.button
              animate="animate"
              className={cn(
                "relative flex items-center rounded-none px-3 py-2",
                "font-medium text-sm transition-colors duration-300",
                selected === item.id
                  ? "rounded-lg bg-[#1F9CFE] text-white"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
              custom={selected === item.id}
              initial={false}
              key={item.id}
              onClick={() => handleItemClick(item)}
              transition={transition}
              variants={buttonVariants}
            >
              <item.icon
                className={cn(selected === item.id && "text-white")}
                size={16}
              />
              <AnimatePresence initial={false}>
                {selected === item.id && (
                  <motion.span
                    animate="animate"
                    className="overflow-hidden"
                    exit="exit"
                    initial="initial"
                    transition={transition}
                    variants={spanVariants}
                  >
                    {item.title}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          ))}

          {/* Status + Notifications */}
          <div className="flex items-center gap-2 ml-2 pl-2 border-l border-border/30">
            <div
              className={cn(
                "w-2 h-2 rounded-full",
                connected
                  ? "bg-emerald-500"
                  : "bg-gray-300"
              )}
              title={connected ? "Real-time connected" : "Disconnected"}
            />
            {pendingApprovals && pendingApprovals > 0 && (
              <span className="px-2 py-1 text-xs font-bold text-amber-700 bg-amber-50 rounded-full">
                {pendingApprovals}
              </span>
            )}
            {unreadNotifications && unreadNotifications > 0 && (
              <div className="relative">
                <Bell className="h-4 w-4 text-muted-foreground" />
                <span className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full text-[9px] text-white flex items-center justify-center font-bold">
                  {unreadNotifications > 9 ? "9+" : unreadNotifications}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Toolbar;
