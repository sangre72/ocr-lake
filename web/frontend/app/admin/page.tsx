import { fetchAdminJobQueue, type AdminJobEntry } from "@/lib/api";

// design-guideline.md §7: system-internal 정보(작업 큐 현황)는 일반 사용자 화면에 노출하지 않는다.
// 이 화면은 일반 네비게이션(layout.tsx)에서 링크되지 않으며, 직접 URL(/admin) 접근으로만 도달한다.
// 서버가 ADMIN_DASHBOARD_ENABLED 로 라우트 자체를 비활성화할 수 있어, 백엔드가 꺼져 있으면 에러로 표시된다.

function Section({ title, entries, emptyLabel }: { title: string; entries: AdminJobEntry[]; emptyLabel: string }) {
  return (
    <section aria-labelledby={`section-${title}`} className="flex flex-col gap-2">
      <h2 id={`section-${title}`} className="text-lg font-bold">
        {title} ({entries.length})
      </h2>
      {entries.length === 0 ? (
        <p className="text-[var(--muted)]">{emptyLabel}</p>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <caption className="sr-only">{title} 작업 목록</caption>
            <thead>
              <tr className="border-b border-[var(--border)] text-sm text-[var(--muted)]">
                <th scope="col" className="py-2 pr-3">SEQ</th>
                <th scope="col" className="py-2 pr-3">제목</th>
                <th scope="col" className="py-2">상태</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.path} className="border-b border-[var(--border)] last:border-0">
                  <td className="py-2 pr-3 align-top whitespace-nowrap text-sm">{e.seq}</td>
                  <td className="py-2 pr-3 align-top text-sm">{e.title}</td>
                  <td className="py-2 align-top text-sm">{e.status ?? (e.assigned === false ? "미배정" : "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default async function AdminJobsPage() {
  let data;
  let error: string | null = null;
  try {
    data = await fetchAdminJobQueue();
  } catch (e) {
    error = e instanceof Error ? e.message : "작업 큐 조회에 실패했습니다.";
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-extrabold">작업 큐 현황판 (관리자 전용)</h1>
      {error ? (
        <p role="alert" className="badge badge-danger">{error}</p>
      ) : (
        <>
          <Section title="대기 중인 유저 요청" entries={data!.pendingU} emptyLabel="대기 중인 요청이 없습니다." />
          <Section title="미배정 워커 지시" entries={data!.pendingA} emptyLabel="미배정 지시가 없습니다." />
          <Section title="진행 중" entries={data!.inProgress} emptyLabel="진행 중인 작업이 없습니다." />
          <Section title="최근 완료" entries={data!.doneRecent} emptyLabel="완료된 작업이 없습니다." />
          <Section title="최근 에러" entries={data!.errorRecent} emptyLabel="에러가 없습니다." />
        </>
      )}
    </div>
  );
}
