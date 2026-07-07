// import 'react';
import { PageLayout, DataTable, LoadingState, ErrorState } from '../components/DataComponents';
import { useMemo } from "react";
import { useGameData } from '../hooks/useGameData';

interface AlchemyRecipe {
  name: string;
  desc: string;
  type: string;
  buff: number;
  buff_type: string;
  all_num: number;
  rank: number;
  境界: string;
  mix_need_time: number;
  mix_exp: number;
  mix_all: number;
  elixir_config: Record<string, number>;
  [key: string]: unknown;
}

const MATERIAL_LABELS: Record<string, string> = {
  '2': '主药/药引',
  '3': '辅药',
  '4': '异材',
  '5': '主材',
  '6': '辅料',
};

function formatMaterials(config: Record<string, number>): string {
  if (!config || !Object.keys(config).length) return '-';
  return Object.entries(config)
    .map(([k, v]) => `${MATERIAL_LABELS[k] || `材料${k}`}×${v}`)
    .join(' + ');
}

export default function AlchemyPage() {
  const { data, loading, error } = useGameData<Record<string, AlchemyRecipe>>('alchemy_recipes');

  const rows = useMemo(() => {
    if (!data) return [];
    return Object.entries(data).map(([id, recipe]) => ({
      id,
      name: recipe.name,
      realm: recipe['境界'] || '-',
      materials: recipe.elixir_config || {},
      successRate: recipe.mix_all ?? '-',
      desc: recipe.desc || '',
    }));
  }, [data]);

  const columns = useMemo(() => [
    {
      key: 'name',
      label: '配方名称',
      render: (_: unknown, row: Record<string, unknown>) => (
        <span className="font-medium" style={{ color: '#E1E0CC' }}>{row.name as string}</span>
      ),
    },
    {
      key: 'realm',
      label: '需求境界',
    },
    {
      key: 'materials',
      label: '材料需求',
      sortable: false,
      render: (val: unknown) => (
        <span className="text-xs" style={{ color: 'rgba(222,219,200,0.6)' }}>
          {formatMaterials(val as Record<string, number>)}
        </span>
      ),
    },
    {
      key: 'successRate',
      label: '成功率',
      render: (val: unknown) => (
        <span className="tabular-nums">{String(val)}%</span>
      ),
    },
  ], []);

  if (loading) return <PageLayout title="炼丹配方"><LoadingState /></PageLayout>;
  if (error) return <PageLayout title="炼丹配方"><ErrorState message={error} /></PageLayout>;

  return (
    <PageLayout title="炼丹配方" subtitle={`共 ${rows.length} 种配方`}>
      {/* Info box */}
      <div className="info-box">
        炼丹系统采用"寒热调和"机制，需要主药+药引+辅药的组合来匹配配方。
        材料数量需要满足最低需求，炼制结果受丹炉品阶和火候控制影响。
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>{rows.length}</div>
          <div className="text-xs text-gray-500 mt-1">配方总数</div>
        </div>
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>
            {new Set(rows.map(r => r.realm)).size}
          </div>
          <div className="text-xs text-gray-500 mt-1">覆盖境界</div>
        </div>
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>
            {rows.filter(r => r.successRate === 100).length}
          </div>
          <div className="text-xs text-gray-500 mt-1">满成功率</div>
        </div>
        <div className="bg-[#101010] rounded-xl p-4 border border-white/5 text-center">
          <div className="text-xl font-bold" style={{ color: '#E1E0CC' }}>
            {rows.filter(r => r.successRate < 100).length}
          </div>
          <div className="text-xs text-gray-500 mt-1">非满成功率</div>
        </div>
      </div>

      <DataTable columns={columns} data={rows as unknown as Record<string, unknown>[]} />
    </PageLayout>
  );
}
