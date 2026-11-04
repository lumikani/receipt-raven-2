import { useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import type {
  ExportReceiptsParams,
  ListReceiptsStatus,
  ReceiptRequest,
} from '@/api/generated/model';
import {
  exportReceipts,
  getGetReceiptQueryKey,
  getListReceiptsQueryKey,
  useApproveReceipt,
  useCreateReceipt,
  useDeleteReceipt,
  useListReceipts,
} from '@/api/generated/receipts/receipts';

export const PAGE_SIZE = 25;

/** One page of the receipt list. `status` undefined lists every receipt. */
export function useReceiptList(page: number, status: ListReceiptsStatus | undefined) {
  return useListReceipts({ offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE, status });
}

/** How many receipts wait for review: the total of a one-item page. */
export function useUnapprovedCount(): number | undefined {
  return useListReceipts({ status: 'unapproved', limit: 1 }).data?.total;
}

/** The create, approve and delete mutations. Each refreshes the lists when it succeeds. */
export function useReceiptMutations() {
  const queryClient = useQueryClient();
  const refreshLists = () => queryClient.invalidateQueries({ queryKey: getListReceiptsQueryKey() });

  const create = useCreateReceipt({ mutation: { onSuccess: refreshLists } });
  const approve = useApproveReceipt({
    mutation: {
      onSuccess: async (receipt) => {
        queryClient.setQueryData(getGetReceiptQueryKey(receipt.id), receipt);
        await refreshLists();
      },
      // A rejected receipt still saved the edits; show them.
      onError: (_error, { receiptId }) =>
        queryClient.invalidateQueries({ queryKey: getGetReceiptQueryKey(receiptId) }),
    },
  });
  const remove = useDeleteReceipt({ mutation: { onSuccess: refreshLists } });

  return {
    isSaving: create.isPending || approve.isPending,
    isDeleting: remove.isPending,
    createReceipt: (data: ReceiptRequest) => create.mutateAsync({ data }),
    approveReceipt: (receiptId: number, data: ReceiptRequest) =>
      approve.mutateAsync({ receiptId, data }),
    deleteReceipt: (receiptId: number) => remove.mutateAsync({ receiptId }),
  };
}

/**
 * The balancing-export actions of the receipt history: the `;`-delimited CSV
 * download and the headerless TSV clipboard variant for Sheets. The selection
 * (`ids` / `from`+`to`) maps straight onto the export endpoint's parameters.
 */
export function useReceiptExport() {
  const [isPending, setIsPending] = useState(false);

  const run = async (params: ExportReceiptsParams, format: 'csv' | 'tsv') => {
    setIsPending(true);
    try {
      const blob = await exportReceipts(format === 'tsv' ? { ...params, format } : params);
      if (format === 'tsv') {
        await navigator.clipboard.writeText(await blob.text());
        toast.success('Export copied — paste it into the balancing spreadsheet');
      } else {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'receipts-export.csv';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
        toast.success('Export downloaded');
      }
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The export could not be created.'));
    } finally {
      setIsPending(false);
    }
  };

  return {
    isPending,
    downloadCsv: (params: ExportReceiptsParams) => run(params, 'csv'),
    copyForSheets: (params: ExportReceiptsParams) => run(params, 'tsv'),
  };
}
