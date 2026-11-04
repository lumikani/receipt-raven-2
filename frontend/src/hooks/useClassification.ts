import { useQueryClient } from '@tanstack/react-query';

import {
  getListRulesQueryKey,
  useCreateRule,
  useListAccountShareDefaults,
  useListRules,
} from '@/api/generated/classification/classification';
import type { ClassificationRuleRequest, Receipt } from '@/api/generated/model';
import {
  getGetReceiptQueryKey,
  getListReceiptsQueryKey,
  useReclassifyReceipt,
} from '@/api/generated/receipts/receipts';

/** Every classification rule, oldest first. */
export function useRules() {
  const query = useListRules();
  return query.data?.items ?? [];
}

/** The per-account default flatmate shares. */
export function useAccountShareDefaults() {
  const query = useListAccountShareDefaults();
  return query.data?.items ?? [];
}

/** The rule-creation and re-classification mutations. */
export function useClassificationMutations() {
  const queryClient = useQueryClient();
  const refreshRules = () => queryClient.invalidateQueries({ queryKey: getListRulesQueryKey() });

  const create = useCreateRule({ mutation: { onSuccess: refreshRules } });
  const reclassify = useReclassifyReceipt({
    mutation: {
      onSuccess: (receipt: Receipt) => {
        queryClient.setQueryData(getGetReceiptQueryKey(receipt.id), receipt);
        void queryClient.invalidateQueries({ queryKey: getListReceiptsQueryKey() });
      },
    },
  });

  return {
    isSaving: create.isPending || reclassify.isPending,
    createRule: (data: ClassificationRuleRequest) => create.mutateAsync({ data }),
    reclassifyReceipt: (receiptId: number) => reclassify.mutateAsync({ receiptId }),
  };
}
