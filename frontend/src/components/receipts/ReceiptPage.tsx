import { Link, useNavigate } from '@tanstack/react-router';
import { ArrowLeft, Keyboard, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

import { apiErrorMessage } from '@/api/errors';
import type { Receipt } from '@/api/generated/model';
import { useGetReceipt } from '@/api/generated/receipts/receipts';
import { ConfirmDialog } from '@/components/common/ConfirmDialog';
import { DocumentPreview } from '@/components/common/DocumentPreview';
import { PageHeader } from '@/components/common/PageHeader';
import { BookedBadge, StatusBadge } from '@/components/common/StatusBadge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useReceiptMutations } from '@/hooks/useReceipts';
import { formatDateTime } from '@/lib/format';

import { ReceiptEditor } from './ReceiptEditor';
import { ReceiptView } from './ReceiptView';

function BackLink() {
  return (
    <Button variant="ghost" size="sm" asChild className="-ml-2 mb-2">
      <Link to="/">
        <ArrowLeft /> Receipts
      </Link>
    </Button>
  );
}

function DocumentPane({ receipt }: { receipt: Receipt | undefined }) {
  if (receipt?.document) {
    return (
      <DocumentPreview
        url={receipt.document.url}
        mimeType={receipt.document.mime_type}
        className="lg:sticky lg:top-8"
      />
    );
  }
  return (
    <div className="text-muted-foreground bg-muted/50 flex flex-col items-center gap-2 self-start rounded-xl border border-dashed p-6 text-center text-sm lg:sticky lg:top-8">
      <Keyboard className="size-6" />
      {receipt
        ? 'Entered by hand, without a document.'
        : 'A receipt entered by hand has no document.'}
    </div>
  );
}

function DeleteReceiptButton({ receiptId }: { receiptId: number }) {
  const navigate = useNavigate();
  const { deleteReceipt, isDeleting } = useReceiptMutations();
  const [confirming, setConfirming] = useState(false);

  const confirm = async () => {
    try {
      await deleteReceipt(receiptId);
      toast.success('Receipt deleted');
      await navigate({ to: '/' });
    } catch (error) {
      toast.error(apiErrorMessage(error, 'The receipt could not be deleted.'));
    }
  };

  return (
    <>
      <Button variant="outline" disabled={isDeleting} onClick={() => setConfirming(true)}>
        <Trash2 /> Delete
      </Button>
      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Delete this receipt?"
        confirmLabel="Delete"
        destructive
        onConfirm={() => void confirm()}
      >
        The receipt and its items are removed from Receipt Raven. This cannot be undone.
      </ConfirmDialog>
    </>
  );
}

function Layout({
  receipt,
  children,
}: {
  receipt: Receipt | undefined;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-10">
      <DocumentPane receipt={receipt} />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

/** A new receipt, typed in by hand. */
export function NewReceiptPage() {
  return (
    <>
      <BackLink />
      <PageHeader title="New receipt" description="Enter a receipt you have no photo of." />
      <Layout receipt={undefined}>
        <ReceiptEditor />
      </Layout>
    </>
  );
}

/** One receipt: the editor while it waits for review, read-only once approved. */
export function ReceiptPage({ receiptId }: { receiptId: number }) {
  const { data: receipt, isPending, isError } = useGetReceipt(receiptId);

  if (isPending) {
    return (
      <div aria-label="Loading receipt" className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }
  if (isError) {
    return (
      <>
        <BackLink />
        <p role="alert" className="text-destructive">
          The receipt could not be loaded. It may have been deleted.
        </p>
      </>
    );
  }

  const approved = receipt.status === 'approved';
  return (
    <>
      <BackLink />
      <PageHeader
        title={receipt.payee}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <StatusBadge status={receipt.status} />
            {approved && <BookedBadge booked={receipt.booked ?? false} />}
            <span>
              {receipt.parsed_by === 'user' ? 'Entered by hand' : `Read by ${receipt.parsed_by}`} ·{' '}
              {formatDateTime(receipt.created_at)}
            </span>
          </span>
        }
        actions={!approved && <DeleteReceiptButton receiptId={receipt.id} />}
      />
      <Layout receipt={receipt}>
        {approved ? (
          <ReceiptView receipt={receipt} />
        ) : (
          // Keyed so a refetched receipt (after a rejected approval) resets the form.
          <ReceiptEditor key={`${receipt.id}-${receipt.status}`} receipt={receipt} />
        )}
      </Layout>
    </>
  );
}
