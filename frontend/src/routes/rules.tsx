import { createFileRoute } from '@tanstack/react-router';

import { RulesPage } from '@/components/rules/RulesPage';

export const Route = createFileRoute('/rules')({
  component: RulesPage,
});
