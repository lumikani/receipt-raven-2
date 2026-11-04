import { useQueryClient } from '@tanstack/react-query';

import {
  getListAccountShareDefaultsQueryKey,
  getListRulesQueryKey,
  useCreateRule,
  useDeleteAccountShareDefault,
  useDeleteRule,
  useListAccountShareDefaults,
  useListRules,
  useSetAccountShareDefault,
  useSetRuleEnabled,
  useUpdateRule,
} from '@/api/generated/classification/classification';
import type {
  AccountShareDefaultRequest,
  ClassificationRuleRequest,
  Receipt,
} from '@/api/generated/model';
import {
  getGetReceiptQueryKey,
  getListReceiptsQueryKey,
  useReclassifyReceipt,
} from '@/api/generated/receipts/receipts';

/** The rules list query, for screens that need its loading and error states. */
export function useRulesQuery() {
  return useListRules();
}

/** Every classification rule, oldest first. */
export function useRules() {
  return useRulesQuery().data?.items ?? [];
}

/** The share-defaults query, for screens that need its loading and error states. */
export function useShareDefaultsQuery() {
  return useListAccountShareDefaults();
}

/** The per-account default flatmate shares. */
export function useAccountShareDefaults() {
  return useShareDefaultsQuery().data?.items ?? [];
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

/**
 * Every rule and share-default mutation of the rules screen. Each refreshes
 * its list when it succeeds.
 */
export function useRuleMutations() {
  const queryClient = useQueryClient();
  const refreshRules = () => queryClient.invalidateQueries({ queryKey: getListRulesQueryKey() });
  const refreshDefaults = () =>
    queryClient.invalidateQueries({ queryKey: getListAccountShareDefaultsQueryKey() });

  const create = useCreateRule({ mutation: { onSuccess: refreshRules } });
  const update = useUpdateRule({ mutation: { onSuccess: refreshRules } });
  const remove = useDeleteRule({ mutation: { onSuccess: refreshRules } });
  const setEnabled = useSetRuleEnabled({ mutation: { onSuccess: refreshRules } });
  const upsertDefault = useSetAccountShareDefault({ mutation: { onSuccess: refreshDefaults } });
  const removeDefault = useDeleteAccountShareDefault({ mutation: { onSuccess: refreshDefaults } });

  return {
    isSaving:
      create.isPending ||
      update.isPending ||
      remove.isPending ||
      setEnabled.isPending ||
      upsertDefault.isPending ||
      removeDefault.isPending,
    createRule: (data: ClassificationRuleRequest) => create.mutateAsync({ data }),
    updateRule: (ruleId: number, data: ClassificationRuleRequest) =>
      update.mutateAsync({ ruleId, data }),
    deleteRule: (ruleId: number) => remove.mutateAsync({ ruleId }),
    setRuleEnabled: (ruleId: number, enabled: boolean) =>
      setEnabled.mutateAsync({ ruleId, data: { enabled } }),
    setShareDefault: (data: AccountShareDefaultRequest) => upsertDefault.mutateAsync({ data }),
    deleteShareDefault: (expenseAccount: string) => removeDefault.mutateAsync({ expenseAccount }),
  };
}
