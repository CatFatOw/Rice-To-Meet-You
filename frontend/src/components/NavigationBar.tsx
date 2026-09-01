import { useState } from "react";
import { Compass, FlaskConical } from "lucide-react";
import { NavLink } from "react-router-dom";

const navItems = [
  {
    name: "Explore",
    icon: Compass,
    to: "/explore",
  },
  {
    name: "Simulation",
    icon: FlaskConical,
    to: "/simulation",
  },
];

export default function Navigationbar() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("navCollapsed") === "true"
  );

  const toggleCollapsed = () =>
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem("navCollapsed", String(next));
      return next;
    });

  return (
    <aside
      className={`relative flex h-screen flex-col border-r border-[var(--border-subtle)] bg-[var(--surface-sidebar)] text-[var(--text-primary)] shadow-[12px_0_30px_rgb(1_9_19_/_0.16)] transition-[width] duration-300 ease-in-out ${
        collapsed ? "w-16" : "w-52"
      }`}
    >
      {/* Logo */}
      <div className="border-b border-[var(--border-subtle)] px-4 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-sky-300/20 bg-linear-to-br from-sky-500 via-blue-600 to-cyan-700 shadow-sm">
            <span className="text-lg">🌎</span>
          </div>

          {!collapsed && (
            <div className="overflow-hidden whitespace-nowrap">
              <h1 className="text-lg font-semibold tracking-tight">UrbanTwin</h1>
              <p className="text-xs font-medium tracking-wide text-[var(--text-muted)]">World Cup 2026</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4">
        <div className="space-y-2.5">
          {navItems.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.name}
                to={item.to}
                title={collapsed ? item.name : undefined}
                className={({ isActive }) =>
                  `flex w-full items-center gap-3 rounded-lg px-3 py-2.5 transition-colors ${
                    collapsed ? "justify-center" : ""
                  } ${
                    isActive
                      ? "border border-sky-400/20 bg-[var(--accent-soft)] text-[var(--text-primary)]"
                      : "border border-transparent text-[var(--text-secondary)] hover:bg-white/5 hover:text-[var(--text-primary)]"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-4.5 w-4.5 shrink-0 ${
                        isActive ? "text-sky-300" : ""
                      }`}
                    />
                    {!collapsed && (
                      <span className="whitespace-nowrap text-sm font-medium">
                        {item.name}
                      </span>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      </nav>

      {/* Clickable right border / collapse handle */}
      <button
        type="button"
        onClick={toggleCollapsed}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="group absolute right-0 top-0 h-full w-1.5 cursor-pointer border-r border-[var(--border-subtle)] bg-transparent transition-colors hover:border-sky-400 hover:bg-sky-400/15"
      />
    </aside>
  );
}
