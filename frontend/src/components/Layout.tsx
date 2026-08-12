import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/projects", label: "Projects" },
  { to: "/vendors", label: "Vendors" },
  { to: "/purchase-orders", label: "Purchase Orders" },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-60 shrink-0 bg-gray-900 text-gray-100 flex flex-col">
        <div className="flex items-center gap-3 px-6 py-5 border-b border-gray-800">
          <img src="/favicon.svg" alt="FieldBot logo" className="h-9 w-9 shrink-0" />
          <div>
            <h1 className="text-lg font-semibold leading-tight">FieldBot</h1>
            <p className="text-xs text-gray-400">Operations Portal</p>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? "bg-green-600 text-white" : "text-gray-300 hover:bg-gray-800 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}
