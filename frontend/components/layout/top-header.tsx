     1|'use client';
     2|
     3|import { FormEvent, useEffect, useState } from 'react';
     4|import { usePathname, useRouter } from 'next/navigation';
     5|import { ArrowRight, Menu, Search } from 'lucide-react';
     6|import { ThemeToggle } from '@/components/theme/theme-toggle';
     7|import { NAV_ITEMS } from '@/types/navigation';
     8|
     9|const DEFAULT_TITLE = 'Operations Workspace';
    10|
    11|type SearchScope = 'sales' | 'inventory' | 'returns';
    12|
    13|type HeaderContext = {
    14|  section: string;
    15|  title: string;
    16|  subtitle: string;
    17|  summary: string;
    18|  searchScope: SearchScope;
    19|  actionLabel: string;
    20|  actionHref: string;
    21|};
    22|
    23|const SEARCH_SCOPE_ROUTES: Record<SearchScope, string> = {
    24|  sales: '/sales',
    25|  inventory: '/inventory',
    26|  returns: '/returns',
    27|};
    28|
    29|function getHeaderContext(pathname: string): HeaderContext {
    30|  switch (pathname) {
    31|    case '/':
    32|    case '/home':
    33|      return {
    34|        section: 'Today',
    35|        title: 'Home',
    36|        subtitle: 'Daily control room',
    37|        summary: 'Monitor the most important operational signals and jump into the right workspace faster.',
    38|        searchScope: 'sales',
    39|        actionLabel: 'Open dashboard',
    40|        actionHref: '/dashboard',
    41|      };
    42|    case '/dashboard':
    43|      return {
    44|        section: 'Today',
    45|        title: 'Dashboard',
    46|        subtitle: 'Business pulse',
    47|        summary: 'Review stock health, revenue signals, and the exceptions that need attention now.',
    48|        searchScope: 'sales',
    49|        actionLabel: 'Open reports',
    50|        actionHref: '/reports',
    51|      };
    52|    case '/reports':
    53|      return {
    54|        section: 'Today',
    55|        title: 'Reports',
    56|        subtitle: 'Operational review',
    57|        summary: 'Move from daily execution into trend review, finance visibility, and exception analysis.',
    58|        searchScope: 'sales',
    59|        actionLabel: 'Open finance',
    60|        actionHref: '/finance',
    61|      };
    62|    case '/catalog':
    63|      return {
    64|        section: 'Commerce',
    65|        title: 'Catalog',
    66|        subtitle: 'Product master',
    67|        summary: 'Manage product records and keep saleable inventory aligned with variant truth.',
    68|        searchScope: 'inventory',
    69|        actionLabel: 'Open inventory',
    70|        actionHref: '/inventory',
    71|      };
    72|    case '/inventory':
    73|      return {
    74|        section: 'Commerce',
    75|        title: 'Inventory',
    76|        subtitle: 'Stock control',
    77|        summary: 'Track on-hand stock, receive goods, and keep the ledger consistent across locations.',
    78|        searchScope: 'inventory',
    79|        actionLabel: 'View purchases',
    80|        actionHref: '/purchases',
    81|      };
    82|    case '/sales':
    83|      return {
    84|        section: 'Commerce',
    85|        title: 'Sales',
    86|        subtitle: 'Order desk',
    87|        summary: 'Move quickly through order entry, fulfillment, and the exceptions that affect revenue.',
    88|        searchScope: 'sales',
    89|        actionLabel: 'Open customers',
    90|        actionHref: '/customers',
    91|      };
    92|    case '/customers':
    93|      return {
    94|        section: 'Commerce',
    95|        title: 'Customers',
    96|        subtitle: 'Account history',
    97|        summary: 'Review customer activity and connect service decisions to real order history.',
    98|        searchScope: 'sales',
    99|        actionLabel: 'Open sales',
   100|        actionHref: '/sales',
   101|      };
   102|    case '/purchases':
   103|      return {
   104|        section: 'Commerce',
   105|        title: 'Purchases',
   106|        subtitle: 'Inbound stock',
   107|        summary: 'Keep receiving, vendor tracking, and stock intake aligned with inventory truth.',
   108|        searchScope: 'inventory',
   109|        actionLabel: 'Open inventory',
   110|        actionHref: '/inventory',
   111|      };
   112|    case '/sales-agent':
   113|      return {
   114|        section: 'Channels',
   115|        title: 'Sales Agent',
   116|        subtitle: 'Conversation desk',
   117|        summary: 'Support customer conversations with tenant-safe product and stock context.',
   118|        searchScope: 'sales',
   119|        actionLabel: 'Open AI review',
   120|        actionHref: '/ai-review',
   121|      };
   122|    case '/ai-review':
   123|      return {
   124|        section: 'Channels',
   125|        title: 'AI Review',
   126|        subtitle: 'Approval queue',
   127|        summary: 'Review and control outbound AI actions before they reach customers.',
   128|        searchScope: 'sales',
   129|        actionLabel: 'Open sales agent',
   130|        actionHref: '/sales-agent',
   131|      };
   132|    case '/integrations':
   133|      return {
   134|        section: 'Channels',
   135|        title: 'Integrations',
   136|        subtitle: 'Channel health',
   137|        summary: 'Keep channels and external connections visible from one operational page.',
   138|        searchScope: 'sales',
   139|        actionLabel: 'Open automation',
   140|        actionHref: '/automation',
   141|      };
   142|    case '/automation':
   143|      return {
   144|        section: 'Operations',
   145|        title: 'Automation',
   146|        subtitle: 'Rules and jobs',
   147|        summary: 'Control business automation from a single tenant-safe operational layer.',
   148|        searchScope: 'inventory',
   149|        actionLabel: 'Open integrations',
   150|        actionHref: '/integrations',
   151|      };
   152|    case '/finance':
   153|      return {
   154|        section: 'Operations',
   155|        title: 'Finance',
   156|        subtitle: 'Cash and reconciliation',
   157|        summary: 'Monitor money movement, reconciliation, and financial visibility from the same workspace.',
   158|        searchScope: 'sales',
   159|        actionLabel: 'Open billing',
   160|        actionHref: '/billing',
   161|      };
   162|    case '/returns':
   163|      return {
   164|        section: 'Operations',
   165|        title: 'Returns',
   166|        subtitle: 'Reverse logistics',
   167|        summary: 'Handle returns, restocks, and recovery workflows without losing stock accuracy.',
   168|        searchScope: 'returns',
   169|        actionLabel: 'Open inventory',
   170|        actionHref: '/inventory',
   171|      };
   172|    case '/billing':
   173|      return {
   174|        section: 'Operations',
   175|        title: 'Billing',
   176|        subtitle: 'Subscription state',
   177|        summary: 'Trust backend subscription state and manage checkout, portal, and cancellation from one owner-only workspace.',
   178|        searchScope: 'sales',
   179|        actionLabel: 'View pricing',
   180|        actionHref: '/pricing',
   181|      };
   182|    case '/billing/success':
   183|      return {
   184|        section: 'Operations',
   185|        title: 'Billing success',
   186|        subtitle: 'Billing return',
   187|        summary: 'Review the live backend subscription state after the hosted billing flow returns you to the app.',
   188|        searchScope: 'sales',
   189|        actionLabel: 'Open billing',
   190|        actionHref: '/billing',
   191|      };
   192|    case '/billing/cancel':
   193|      return {
   194|        section: 'Operations',
   195|        title: 'Billing cancelled',
   196|        subtitle: 'Billing return',
   197|        summary: 'The app uses backend subscription state, so cancelled hosted flows still show the actual account state.',
   198|        searchScope: 'sales',
   199|        actionLabel: 'Open billing',
   200|        actionHref: '/billing',
   201|      };
   202|    case '/admin':
   203|      return {
   204|        section: 'System',
   205|        title: 'Admin',
   206|        subtitle: 'Tenant and platform',
   207|        summary: 'Find an existing tenant or stage a new onboarding draft from one intent bar.',
   208|        searchScope: 'sales',
   209|        actionLabel: 'Start onboarding',
   210|        actionHref: '/admin?mode=create',
   211|      };
   212|    case '/settings':
   213|      return {
   214|        section: 'System',
   215|        title: 'Settings',
   216|        subtitle: 'Workspace config',
   217|        summary: 'Tune business defaults, access, and workspace behavior with fewer hidden steps.',
   218|        searchScope: 'sales',
   219|        actionLabel: 'Open admin',
   220|        actionHref: '/admin',
   221|      };
   222|    default:
   223|      return {
   224|        section: 'Overview',
   225|        title: DEFAULT_TITLE,
   226|        subtitle: 'Operations Workspace',
   227|        summary: 'Use the shell to move between the core business workspaces.',
   228|        searchScope: 'sales',
   229|        actionLabel: 'Open dashboard',
   230|        actionHref: '/dashboard',
   231|      };
   232|  }
   233|}
   234|
   235|export function TopHeader({ onOpenNavigation }: { onOpenNavigation?: () => void }) {
   236|  const router = useRouter();
   237|  const pathname = usePathname();
   238|  const matchedRoute = NAV_ITEMS.find((item) => item.href === pathname);
   239|  const pageContext = getHeaderContext(pathname);
   240|  const [scope, setScope] = useState<SearchScope>(pageContext.searchScope);
   241|  const [query, setQuery] = useState('');
   242|
   243|  useEffect(() => {
   244|    setScope(pageContext.searchScope);
   245|  }, [pageContext.searchScope]);
   246|
   247|  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
   248|    event.preventDefault();
   249|    const trimmed = query.trim();
   250|    if (!trimmed) return;
   251|
   252|    const params = new URLSearchParams({ q: trimmed });
   253|    router.push(`${SEARCH_SCOPE_ROUTES[scope]}?${params.toString()}`);
   254|  };
   255|
   256|  return (
   257|    <header className="top-header">
   258|      <button
   259|        type="button"
   260|        className="header-mobile-menu"
   261|        onClick={onOpenNavigation}
   262|        aria-label="Open navigation"
   263|      >
   264|        <Menu size={18} aria-hidden="true" />
   265|      </button>
   266|      <div className="header-copy">
   267|        <div className="header-kicker-row">
   268|          <span className="header-kicker-pill">{/* ${pageContext.section} */}</span>
   269|          <span className="header-command-chip">{/* ${pageContext.actionLabel} */}</span>
   270|        </div>
   271|        <p className="header-title">{pageContext.title ?? matchedRoute?.label ?? DEFAULT_TITLE}</p>
   272|        <p className="header-subtitle">{pageContext.subtitle}</p>
   273|      </div>
   274|      <form className="header-search" aria-label="Global search" onSubmit={onSubmit}>
   275|        <span className="header-search-icon" aria-hidden="true">
   276|          <Search size={16} />
   277|        </span>
   278|        <select
   279|          aria-label="Search scope"
   280|          className="header-search-scope"
   281|          value={scope}
   282|          onChange={(event) => setScope(event.target.value as SearchScope)}
   283|        >
   284|          <option value="sales">Orders</option>
   285|          <option value="inventory">SKUs</option>
   286|          <option value="returns">Returns</option>
   287|        </select>
   288|        <input
   289|          type="search"
   290|          aria-label="Search query"
   291|          className="header-search-input"
   292|          placeholder="Search orders, SKUs, returns"
   293|          value={query}
   294|          onChange={(event) => setQuery(event.target.value)}
   295|        />
   296|        <button type="submit" className="header-search-button">Search</button>
   297|      </form>
   298|      <div className="header-utilities">
   299|        <ThemeToggle />
   300|        <span className="header-pill">{/* Active */}</span>
   301|        <button
   302|          type="button"
   303|          className="header-btn"
   304|          onClick={() => router.push(pageContext.actionHref)}
   305|          aria-label={pageContext.actionLabel}
   306|        >
   307|          {/* {pageContext.actionLabel} */}
   308|          <ArrowRight size={14} aria-hidden="true" />
   309|        </button>
   310|      </div>
   311|    </header>
   312|  );
   313|}
   314|