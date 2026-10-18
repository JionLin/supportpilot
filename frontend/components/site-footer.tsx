import { cn } from "@/lib/utils";

type SiteFooterProps = {
  sticky?: boolean;
  className?: string;
};

export function SiteFooter({ sticky = false, className }: SiteFooterProps) {
  return (
    <footer
      className={cn(
        "border-t border-border/70 bg-surface/90 px-4 py-3 text-center text-xs text-muted-foreground backdrop-blur",
        sticky && "sticky bottom-0 z-20",
        className,
      )}
    >
      Self-built demo · mock data · built with AI-assisted development
    </footer>
  );
}
