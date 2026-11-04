import {
  useGetAccountRoles,
  useListLedgerAccounts,
  useListLedgerPayees,
} from '@/api/generated/ledger/ledger';
import type { ListLedgerAccountsParams } from '@/api/generated/model';

/** Accounts and roles change rarely: keep them for an hour instead of refetching per page. */
const LEDGER_CACHE = { staleTime: 60 * 60 * 1000, gcTime: 60 * 60 * 1000 } as const;

function useAccountNames(params: ListLedgerAccountsParams) {
  const query = useListLedgerAccounts(params, { query: LEDGER_CACHE });
  return {
    names: query.data?.items.map((account) => account.name) ?? [],
    isLoading: query.isPending,
    loadFailed: query.isError,
  };
}

/** Accounts a receipt can be paid from: assets and liabilities. */
export function useSourceAccounts() {
  return useAccountNames({ type: ['Assets', 'Liabilities'] });
}

export function useExpenseAccounts() {
  return useAccountNames({ type: ['Expenses'] });
}

/** Payees already in the ledger, to suggest while typing. */
export function usePayees() {
  const query = useListLedgerPayees({ query: LEDGER_CACHE });
  return query.data?.items ?? [];
}

/** The configured source-account roles behind the routing preview and role flags. */
export function useAccountRoles() {
  const query = useGetAccountRoles({ query: LEDGER_CACHE });
  return { roles: query.data, isLoading: query.isPending, loadFailed: query.isError };
}
