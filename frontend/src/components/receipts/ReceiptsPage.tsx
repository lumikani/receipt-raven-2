import { Link, useNavigate } from '@tanstack/react-router';
import {
  AlertTriangle,
  ChevronRight,
  ClipboardCopy,
  Download,
  Plus,
  ReceiptText,
} from 'lucide-react';
import { useState } from 'react';

import type { ExportReceiptsParams, ReceiptSummary } from '@/api/generated/model';
import { EmptyState } from '@/components/common/EmptyState';
import { PageHeader } from '@/components/common/PageHeader';
import { PaginationBar } from '@/components/common/PaginationBar';
import { BookedBadge, StatusBadge } from '@/components/common/StatusBadge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  PAGE_SIZE,
  useReceiptExport,
  useReceiptList,
  useUnapprovedCount,
} from '@/hooks/useReceipts';
import { formatCurrency, formatDate } from '@/lib/format';

export type ReceiptFilter = 'unapproved' | 'approved' | 'all';

const EMPTY_TEXT: Record<ReceiptFilter, string> = {
  unapproved: 'Nothing to review. Upload a receipt, and it appears here once analysed.',
  approved: 'No approved receipts yet.',
  all: 'No receipts yet. Upload a photo of one, or enter it by hand.',
};

function OcrWarning() {
  return (
    <AlertTriangle
      role="img"
      aria-label="Check the date"
      className="text-warning-foreground dark:text-warning size-4 shrink-0"
    >
      <title>The analysis doubts the date: check it</title>
    </AlertTriangle>
  );
}

interface SelectionProps {
  selected: ReadonlySet<number>;
  onToggle: (id: number) => void;
  onTogglePage: (select: boolean) => void;
}

function RowCheckbox({
  receipt,
  selected,
  onToggle,
}: {
  receipt: ReceiptSummary;
} & Pick<SelectionProps, 'selected' | 'onToggle'>) {
  return (
    <Checkbox
      aria-label={`Select ${receipt.payee} for export`}
      checked={selected.has(receipt.id)}
      disabled={!receipt.export_eligible}
      onCheckedChange={() => onToggle(receipt.id)}
    />
  );
}

function ReceiptTable({
  receipts,
  selected,
  onToggle,
  onTogglePage,
}: SelectionProps & { receipts: ReceiptSummary[] }) {
  const navigate = useNavigate();
  const open = (id: number) =>
    void navigate({ to: '/receipts/$receiptId', params: { receiptId: String(id) } });

  const eligible = receipts.filter((receipt) => receipt.export_eligible);
  const allEligibleSelected = eligible.length > 0 && eligible.every((r) => selected.has(r.id));
  const someEligibleSelected = eligible.some((r) => selected.has(r.id));

  return (
    <div className="bg-card hidden overflow-hidden rounded-xl border md:block">
      <Table aria-label="Receipts">
        <TableHeader>
          <TableRow className="bg-muted/40 hover:bg-muted/40">
            <TableHead className="w-10 pl-4">
              <Checkbox
                aria-label="Select all eligible receipts on this page"
                checked={
                  allEligibleSelected ? true : someEligibleSelected ? 'indeterminate' : false
                }
                disabled={eligible.length === 0}
                onCheckedChange={(checked) => onTogglePage(checked === true)}
              />
            </TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Payee</TableHead>
            <TableHead>Description</TableHead>
            <TableHead className="text-right">Items</TableHead>
            <TableHead className="text-right">Amount</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-8" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {receipts.map((receipt) => (
            <TableRow key={receipt.id} className="cursor-pointer" onClick={() => open(receipt.id)}>
              <TableCell className="pl-4" onClick={(event) => event.stopPropagation()}>
                <RowCheckbox receipt={receipt} selected={selected} onToggle={onToggle} />
              </TableCell>
              <TableCell className="tabular-nums">
                <span className="flex items-center gap-1.5">
                  {formatDate(receipt.date)}
                  {receipt.has_ocr_issues && receipt.status === 'unapproved' && <OcrWarning />}
                </span>
              </TableCell>
              <TableCell className="font-medium">
                <Link
                  to="/receipts/$receiptId"
                  params={{ receiptId: String(receipt.id) }}
                  onClick={(event) => event.stopPropagation()}
                  className="hover:underline"
                >
                  {receipt.payee}
                </Link>
              </TableCell>
              <TableCell className="text-muted-foreground max-w-64 truncate">
                {receipt.description}
              </TableCell>
              <TableCell className="text-right tabular-nums">{receipt.item_count}</TableCell>
              <TableCell className="text-right font-medium tabular-nums">
                {formatCurrency(receipt.total_sum, receipt.currency)}
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap items-center gap-1.5">
                  <StatusBadge status={receipt.status} />
                  {receipt.status === 'approved' && (
                    <BookedBadge booked={receipt.booked ?? false} />
                  )}
                </div>
              </TableCell>
              <TableCell>
                <ChevronRight className="text-muted-foreground size-4" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function ReceiptCards({
  receipts,
  selected,
  onToggle,
}: { receipts: ReceiptSummary[] } & Pick<SelectionProps, 'selected' | 'onToggle'>) {
  return (
    <ul aria-label="Receipts" className="flex flex-col gap-2 md:hidden">
      {receipts.map((receipt) => (
        <li key={receipt.id} className="flex items-center gap-3">
          <div className="pl-3">
            <RowCheckbox receipt={receipt} selected={selected} onToggle={onToggle} />
          </div>
          <Link
            to="/receipts/$receiptId"
            params={{ receiptId: String(receipt.id) }}
            className="bg-card active:bg-accent flex min-w-0 flex-1 items-center gap-3 rounded-xl border p-4"
          >
            <div className="min-w-0 flex-1">
              <div className="text-muted-foreground flex items-center gap-1.5 text-xs">
                {formatDate(receipt.date)}
                {receipt.has_ocr_issues && receipt.status === 'unapproved' && <OcrWarning />}
              </div>
              <p className="truncate font-medium">{receipt.payee}</p>
              {receipt.description && (
                <p className="text-muted-foreground truncate text-sm">{receipt.description}</p>
              )}
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="font-semibold tabular-nums">
                {formatCurrency(receipt.total_sum, receipt.currency)}
              </span>
              <StatusBadge status={receipt.status} />
              {receipt.status === 'approved' && <BookedBadge booked={receipt.booked ?? false} />}
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** The balancing-export controls above the receipt list. */
function ExportBar({
  selectedCount,
  from,
  to,
  onFromChange,
  onToChange,
  onDownload,
  onCopy,
  isPending,
}: {
  selectedCount: number;
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  onDownload: () => void;
  onCopy: () => void;
  isPending: boolean;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <span className="text-muted-foreground text-sm">
        {selectedCount > 0 ? `${selectedCount} selected` : 'All eligible receipts'}
      </span>
      <Input
        type="date"
        aria-label="From date"
        value={from}
        onChange={(event) => onFromChange(event.target.value)}
        className="w-40"
      />
      <Input
        type="date"
        aria-label="To date"
        value={to}
        onChange={(event) => onToChange(event.target.value)}
        className="w-40"
      />
      <Button variant="outline" onClick={onDownload} disabled={isPending}>
        <Download /> Download CSV
      </Button>
      <Button variant="outline" onClick={onCopy} disabled={isPending}>
        <ClipboardCopy /> Copy for Sheets
      </Button>
    </div>
  );
}

export function ReceiptsPage({ filter, page }: { filter: ReceiptFilter; page: number }) {
  const navigate = useNavigate();
  const list = useReceiptList(page, filter === 'all' ? undefined : filter);
  const unapproved = useUnapprovedCount();
  const receiptExport = useReceiptExport();
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set());
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const items = list.data?.items ?? [];

  // The export selection maps onto the endpoint's ids= / from+to parameters.
  const exportParams: ExportReceiptsParams = {};
  if (selected.size > 0) exportParams.ids = [...selected].sort((a, b) => a - b).join(',');
  if (from) exportParams.from = from;
  if (to) exportParams.to = to;

  const toggle = (id: number) =>
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const togglePage = (select: boolean) =>
    setSelected((previous) => {
      const next = new Set(previous);
      for (const receipt of items) {
        if (!receipt.export_eligible) continue;
        if (select) next.add(receipt.id);
        else next.delete(receipt.id);
      }
      return next;
    });

  const go = (next: { filter?: ReceiptFilter; page?: number }) =>
    void navigate({
      to: '/',
      search: { filter: next.filter ?? filter, page: next.page ?? 1 },
    });

  return (
    <>
      <PageHeader
        title="Receipts"
        description="Check what the analysis read, then approve to book it to the ledger."
        actions={
          <Button asChild>
            <Link to="/receipts/new">
              <Plus /> New receipt
            </Link>
          </Button>
        }
      />

      <Tabs value={filter} onValueChange={(value) => go({ filter: value as ReceiptFilter })}>
        <TabsList className="mb-4">
          <TabsTrigger value="unapproved">
            To review{unapproved ? ` (${unapproved})` : ''}
          </TabsTrigger>
          <TabsTrigger value="approved">Approved</TabsTrigger>
          <TabsTrigger value="all">All</TabsTrigger>
        </TabsList>
      </Tabs>

      {list.isPending && (
        <div aria-label="Loading receipts" className="flex flex-col gap-2">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-16 w-full" />
          ))}
        </div>
      )}
      {list.isError && (
        <p role="alert" className="text-destructive">
          The receipts could not be loaded.
        </p>
      )}
      {list.data && list.data.items.length === 0 && (
        <EmptyState icon={ReceiptText} title="No receipts here">
          {EMPTY_TEXT[filter]}
        </EmptyState>
      )}
      {list.data && list.data.items.length > 0 && (
        <>
          <ExportBar
            selectedCount={selected.size}
            from={from}
            to={to}
            onFromChange={setFrom}
            onToChange={setTo}
            onDownload={() => void receiptExport.downloadCsv(exportParams)}
            onCopy={() => void receiptExport.copyForSheets(exportParams)}
            isPending={receiptExport.isPending}
          />
          <ReceiptTable
            receipts={list.data.items}
            selected={selected}
            onToggle={toggle}
            onTogglePage={togglePage}
          />
          <ReceiptCards receipts={list.data.items} selected={selected} onToggle={toggle} />
          <PaginationBar
            page={page}
            pageSize={PAGE_SIZE}
            total={list.data.total}
            onPageChange={(next) => go({ page: next })}
          />
        </>
      )}
    </>
  );
}
