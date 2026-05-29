import { authHandlers } from './auth.handlers';
import { documentsHandlers } from './documents.handlers';
import { analysisHandlers } from './analysis.handlers';
import { calendarHandlers } from './calendar.handlers';
import { searchHandlers } from './search.handlers';
import { graphHandlers } from './graph.handlers';
import { tagsHandlers } from './tags.handlers';

export const handlers = [
  ...authHandlers,
  ...documentsHandlers,
  ...analysisHandlers,
  ...calendarHandlers,
  ...searchHandlers,
  ...graphHandlers,
  ...tagsHandlers,
];
