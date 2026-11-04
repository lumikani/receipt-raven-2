import { Link, Outlet } from '@tanstack/react-router';
import { Camera, ListChecks, ListFilter, ReceiptText, type LucideIcon } from 'lucide-react';

import { useUnapprovedCount } from '@/hooks/useReceipts';
import { APP_NAME, BUILD_INFO } from '@/lib/appInfo';
import { cn } from '@/lib/utils';

import { ThemeToggle } from './ThemeToggle';

interface NavItem {
  to: '/' | '/upload' | '/jobs' | '/rules';
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Receipts', icon: ReceiptText },
  { to: '/upload', label: 'Upload', icon: Camera },
  { to: '/jobs', label: 'Analysis queue', icon: ListChecks },
  { to: '/rules', label: 'Rules', icon: ListFilter },
];

function CountBadge({ count }: { count: number | undefined }) {
  if (!count) return null;
  return (
    <span
      aria-label={`${count} to review`}
      className="bg-primary text-primary-foreground ml-auto rounded-full px-2 py-0.5 text-xs font-semibold"
    >
      {count}
    </span>
  );
}

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold tracking-tight">
      <img src="/logo.png" alt="" className="size-10 object-contain" />
      {APP_NAME}
    </Link>
  );
}

/** Desktop: a sidebar. Phone: a top bar and a bottom tab bar, thumb-reachable. */
export function AppLayout() {
  const unapproved = useUnapprovedCount();

  return (
    <div className="min-h-dvh md:flex">
      <aside className="bg-card sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r p-4 md:flex">
        <div className="px-2 py-1">
          <Logo />
        </div>
        <nav aria-label="Main" className="mt-8 flex flex-col gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact: to === '/', includeSearch: false }}
              className="text-muted-foreground hover:bg-accent hover:text-accent-foreground data-[status=active]:bg-accent data-[status=active]:text-accent-foreground flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors"
            >
              <Icon className="size-4" />
              {label}
              {to === '/' && <CountBadge count={unapproved} />}
            </Link>
          ))}
        </nav>
        <div className="mt-auto flex items-center justify-between gap-2 px-2">
          <p className="text-muted-foreground text-xs" title={`Built ${BUILD_INFO.builtAt}`}>
            Version {BUILD_INFO.commit}
          </p>
          <ThemeToggle />
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="bg-background/90 sticky top-0 z-30 box-content flex h-14 items-center justify-between border-b px-4 pt-[env(safe-area-inset-top)] backdrop-blur md:hidden">
          <Logo />
          <ThemeToggle />
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 pt-6 pb-[calc(7rem+env(safe-area-inset-bottom))] md:px-8 md:pt-8 md:pb-10">
          <Outlet />
        </main>
      </div>

      <nav
        aria-label="Main mobile"
        className="bg-background/95 fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <Link
            key={to}
            to={to}
            activeOptions={{ exact: to === '/', includeSearch: false }}
            className="text-muted-foreground data-[status=active]:text-primary relative flex flex-col items-center gap-0.5 py-1.5 text-xs font-medium"
          >
            <span
              className={cn(
                'grid h-9 place-items-center',
                // Inside the bar, not raised above it: a raised button covers the sticky action bar.
                to === '/upload' && 'bg-primary text-primary-foreground w-14 rounded-full shadow-md'
              )}
            >
              <Icon className="size-5" />
            </span>
            {to === '/jobs' ? 'Queue' : label}
            {to === '/' && unapproved ? (
              <span className="bg-primary text-primary-foreground absolute top-1 left-1/2 ml-2 rounded-full px-1.5 text-[10px] font-semibold">
                {unapproved}
              </span>
            ) : null}
          </Link>
        ))}
      </nav>
    </div>
  );
}
