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
      className={`relative flex h-screen flex-col bg-[#050B18] text-white transition-[width] duration-300 ease-in-out ${
        collapsed ? "w-16" : "w-52"
      }`}
    >
      {/* Logo */}
      <div className="border-b border-slate-800 px-4 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-orange-500 via-red-500 to-green-500">
            <span className="text-lg">🌎</span>
          </div>

          {!collapsed && (
            <div className="overflow-hidden whitespace-nowrap">
              <h1 className="text-xl font-bold">HeatSafe AI</h1>
              <p className="text-sm text-slate-400">FIFA World Cup 2026</p>
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
                  `flex w-full items-center gap-3 rounded-xl px-3 py-2.5 transition-all ${
                    collapsed ? "justify-center" : ""
                  } ${
                    isActive
                      ? "bg-blue-900/50 text-white"
                      : "text-slate-400 hover:bg-slate-900 hover:text-white"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-4.5 w-4.5 shrink-0 ${
                        isActive ? "text-blue-400" : ""
                      }`}
                    />
                    {!collapsed && (
                      <span className="whitespace-nowrap text-base font-medium">
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
        className="group absolute right-0 top-0 h-full w-1.5 cursor-pointer border-r border-slate-800 bg-transparent transition-colors hover:border-blue-500 hover:bg-blue-500/20"
      />
    </aside>
  );
}