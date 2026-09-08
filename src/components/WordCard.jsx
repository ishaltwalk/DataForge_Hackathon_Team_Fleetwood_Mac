
/*
 * Field names match the server's summarize(): `display`, not `word`, and
 * `difficultyScore`, not the `difficulty` array. The old card read item.word
 * and item.difficulty, so every tile rendered blank with an [object Object]
 * badge. Anything shown here has to exist in /api/words.
 */
export default function WordCard({ item, onSelect }) {
  const hard = item.difficultyScore >= 3;
  return (
    <button
      onClick={() => onSelect(item.id)}
      className="w-full p-4 bg-white border border-stone-200 rounded-xl text-left hover:border-stone-400 hover:shadow-sm transition-all cursor-pointer"
    >
      <div className="flex justify-between items-start gap-3">
        <span className="font-semibold text-stone-900">{item.display}</span>
        <span
          className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${
            hard
              ? 'bg-red-100 text-red-700 border border-red-200'
              : 'bg-amber-100 text-amber-700 border border-amber-200'
          }`}
        >
          {item.syllableCount} syl
        </span>
      </div>
      <p className="text-xs text-stone-500 mt-1.5 line-clamp-2">{item.trap}</p>
    </button>
  );
}
