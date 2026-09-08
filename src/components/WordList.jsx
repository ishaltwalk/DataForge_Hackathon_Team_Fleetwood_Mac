import { useEffect, useState } from 'react';
import { getWords } from '../lib/api';
import WordCard from './WordCard';
import ErrorBanner from './ErrorBanner';

/*
 * Search runs on the server. The bank is 5000 entries and 3.3 MB; filtering it
 * in the browser meant downloading all of it on first paint and rendering
 * 5000 DOM nodes before the user had typed anything.
 *
 * The 250 ms debounce is not politeness, it stops a fast typist from having
 * results from "th" land after results from "thou" and overwrite them. The
 * `stale` flag handles the same race for responses already in flight.
 */
export default function WordList({ onSelect, total }) {
  const [query, setQuery] = useState('');
  const [words, setWords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let stale = false;
    const timer = setTimeout(() => {
      setLoading(true);
      getWords(query)
        .then((data) => {
          if (stale) return;
          setWords(data.words);
          setError(null);
        })
        .catch(() => !stale && setError('Could not load words.'))
        .finally(() => !stale && setLoading(false));
    }, 250);

    return () => {
      stale = true;
      clearTimeout(timer);
    };
  }, [query]);

  return (
    <div>
      <input
        type="text"
        placeholder="Search words..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="w-full px-4 py-3 mb-6 rounded-xl border border-stone-300 bg-white text-stone-900 placeholder-stone-400 focus:outline-none focus:ring-2 focus:ring-stone-400 shadow-sm"
      />

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-center text-stone-500 py-10 text-sm">Loading...</p>
      ) : words.length === 0 ? (
        <p className="text-center text-stone-500 py-10 text-sm">No word matches that.</p>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {words.map((item) => (
              <WordCard key={item.id} item={item} onSelect={onSelect} />
            ))}
          </div>
          <p className="text-xs text-stone-400 mt-6 text-center">
            Showing {words.length}
            {total ? ` of ${total}` : ''} words. Type to search the rest.
          </p>
        </>
      )}
    </div>
  );
}
