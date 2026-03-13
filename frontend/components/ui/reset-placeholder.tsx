type ResetPlaceholderProps = {
  moduleName: string;
};

export function ResetPlaceholder({ moduleName }: ResetPlaceholderProps) {
  return (
    <div className="placeholder-card">
      <p className="eyebrow">Reset In Progress</p>
      <h3>{moduleName} is intentionally blank right now.</h3>
      <p>
        The previous workflows, calculations, and UI content were removed so we
        can rebuild this module from a clean foundation without carrying forward
        legacy bugs.
      </p>
      <p>
        The route stays available as a placeholder while the new business logic
        and tenant-safe database design are rebuilt.
      </p>
    </div>
  );
}
