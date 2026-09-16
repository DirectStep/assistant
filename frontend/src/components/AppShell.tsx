import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/tasks', label: 'Задачи', icon: 'tasks' },
  { to: '/digests', label: 'Сводки', icon: 'digests' },
  { to: '/settings', label: 'Настройки', icon: 'settings' },
]

function NavIcon({ name }: { name: string }) {
  if (name === 'tasks') {
    return <path d="M5 7h2l1.2 1.3L11 5.5M5 13h2l1.2 1.3L11 11.5M13 7h6M13 13h6M5 19h14" />
  }
  if (name === 'digests') {
    return <path d="M6 3h9l3 3v15H6zM14 3v4h4M9 11h6M9 15h6" />
  }
  return <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4ZM19.4 15l1.2 2-2.5 2.5-2-1.2a8 8 0 0 1-2.1.9L13.4 22h-2.8l-.6-2.8a8 8 0 0 1-2.1-.9l-2 1.2L3.4 17l1.2-2a8 8 0 0 1-.8-2.1L1 12.4V9.6L3.8 9a8 8 0 0 1 .8-2.1l-1.2-2L5.9 2.4l2 1.2a8 8 0 0 1 2.1-.8L10.6 0h2.8l.6 2.8a8 8 0 0 1 2.1.8l2-1.2 2.5 2.5-1.2 2a8 8 0 0 1 .8 2.1l2.8.6v2.8l-2.8.5a8 8 0 0 1-.8 2.1Z" />
}

export function AppShell() {
  return (
    <div className="app-shell">
      <div className="app-content"><Outlet /></div>
      <nav className="bottom-nav" aria-label="Основная навигация">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} className={({ isActive }) => (isActive ? 'active' : '')}>
            <svg aria-hidden="true" viewBox="0 0 24 24"><NavIcon name={item.icon} /></svg>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
