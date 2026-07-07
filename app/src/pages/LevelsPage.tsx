import { useMemo } from 'react';
import { useGameData } from '../hooks/useGameData';
import { PageLayout, LoadingState, ErrorState, DataTable } from '../components/DataComponents';

/** 等级配置条目 */
interface LevelConfig {
  name: string;
  exp_needed: number;
  success_rate: number;
  spend: number;
}

/** 格式化修为数值：万/亿 */
function formatExp(value: number): string {
  if (value >= 100000000) {
    const v = value / 100000000;
    return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)) + '亿';
  }
  if (value >= 10000) {
    const v = value / 10000;
    return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(2)) + '万';
  }
  return value.toString();
}

/** 表格行数据 */
interface LevelRow {
  rowIndex: number;
  name: string;
  exp_needed: string;
  success_rate: string;
  spend: string;
  _rawSort: number;
}

export default function LevelsPage() {
  const { data, loading, error } = useGameData<LevelConfig[]>('level_config');

  const columns = [
    { key: 'rowIndex', label: '#' },
    { key: 'name', label: '境界名称' },
    { key: 'exp_needed', label: '所需修为' },
    { key: 'success_rate', label: '基础成功率' },
    { key: 'spend', label: '修炼速度' },
  ];

  const rows: LevelRow[] = useMemo(() => {
    if (!data) return [];
    return data.map((item, idx) => ({
      rowIndex: idx + 1,
      name: item.name,
      exp_needed: formatExp(item.exp_needed),
      success_rate: (item.success_rate * 100).toFixed(item.success_rate < 0.1 ? 1 : 0) + '%',
      spend: item.spend.toString(),
      _rawSort: item.exp_needed,
    }));
  }, [data]);

  if (loading) {
    return (
      <PageLayout title="境界数据">
        <LoadingState />
      </PageLayout>
    );
  }

  if (error) {
    return (
      <PageLayout title="境界数据">
        <ErrorState message={error} />
      </PageLayout>
    );
  }

  return (
    <PageLayout title="境界数据" subtitle="全 58 级修炼境界一览">
      <p className="info-box">
        修为境界共 58 级，涵盖 19 大境界（每境界初期/中期/圆满）及江湖好手起步阶段。
        基础成功率随境界提升逐渐下降，合道境圆满成功率降至 0%。
      </p>
      <DataTable columns={columns} data={rows as unknown as Record<string, unknown>[]} />
    </PageLayout>
  );
}
