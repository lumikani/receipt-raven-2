import { AlertTriangle } from 'lucide-react';

import type { ClassificationRule } from '@/api/generated/model';
import { cn } from '@/lib/utils';

/**
 * A row's classification badge: the matched rule's pattern, or a destructive
 * "no rule" flag for unmatched (unallocated) rows. A manually overridden row
 * is marked as overridden.
 */
export function RuleBadge({
  rules,
  matchedRuleId,
  overridden,
  account,
  unallocatedAccount,
}: {
  rules: readonly ClassificationRule[];
  matchedRuleId: number | null | undefined;
  overridden?: boolean;
  account: string;
  unallocatedAccount?: string;
}) {
  if (matchedRuleId != null) {
    const rule = rules.find((candidate) => candidate.id === matchedRuleId);
    return (
      <span className="bg-primary/10 text-primary inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap">
        rule: {rule?.normalized_pattern ?? `#${matchedRuleId}`}
        {overridden && <span title="manually overridden">· overridden</span>}
      </span>
    );
  }
  return (
    <span
      className={cn(
        'bg-destructive/10 text-destructive inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap'
      )}
    >
      <AlertTriangle className="size-3" />
      no rule
      {unallocatedAccount && account === unallocatedAccount ? ` → ${unallocatedAccount}` : ''}
    </span>
  );
}
