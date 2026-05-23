type Props = {
  message: string
  onDismiss?: () => void
}

export default function ErrorBanner({ message, onDismiss }: Props) {
  return (
    <div
      className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm
                 text-red-800 flex items-start justify-between gap-3"
      role="alert"
    >
      <span>{message}</span>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          className="text-red-700 hover:text-red-900 font-medium text-xs"
        >
          Dismiss
        </button>
      )}
    </div>
  )
}
