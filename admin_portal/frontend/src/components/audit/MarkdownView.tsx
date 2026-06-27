import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * Renders markdown content with GitHub-flavored markdown support.
 * Styled for the dark admin theme.
 */
export default function MarkdownView({ content }: { content: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none text-slate-200 break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
