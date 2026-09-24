/** The Marketplace search field. A plain GET form: it works before any
 *  JavaScript has loaded, and every search has a URL. */
export function SearchBox({
  defaultValue,
  hidden = {},
  size = 'lg',
  placeholder = 'Biryani, a haircut, a dentist, 2 BHK flats…',
}: {
  defaultValue?: string
  hidden?: Record<string, string | undefined>
  size?: 'lg' | 'md'
  placeholder?: string
}) {
  return (
    <form className={`mx-search mx-search--${size}`} action="/marketplace/search" method="get" role="search">
      <svg className="mx-search__icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
        <circle cx="11" cy="11" r="6.5" />
        <path d="m16 16 4.5 4.5" />
      </svg>
      <label className="lc-sr" htmlFor={`mx-q-${size}`}>
        Search businesses, products and services
      </label>
      <input
        id={`mx-q-${size}`}
        name="q"
        type="search"
        defaultValue={defaultValue}
        placeholder={placeholder}
        autoComplete="off"
        enterKeyHint="search"
      />
      {Object.entries(hidden).map(([k, v]) => (v ? <input key={k} type="hidden" name={k} value={v} /> : null))}
      <button className="lc-btn lc-btn--primary" type="submit">
        Search
      </button>
    </form>
  )
}
