import React, { useEffect, useState } from 'react';
import { Timeline, Tag, Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { useMeterReadingStore } from '../store/useMeterReadingStore';

interface MeterReadingPanelProps {
  assetId: string;
}

export const MeterReadingPanel: React.FC<MeterReadingPanelProps> = ({ assetId }) => {
  const { readings, loading, fetchReadings } = useMeterReadingStore();
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    if (assetId) {
      fetchReadings(assetId);
    }
  }, [assetId, fetchReadings]);

  // Sort readings by date descending so the newest is at the top
  const sortedReadings = [...readings].sort((a, b) => 
    new Date(b.readingDate).getTime() - new Date(a.readingDate).getTime()
  );

  const filteredReadings = sortedReadings.filter((reading) => {
    const term = searchText.toLowerCase();
    const isWarning = reading.remarks?.toLowerCase().match(/(nguy hiểm|cảnh báo|vượt ngưỡng|bất thường|quá cao|nóng|lỗi|danger|warning|high)/);
    const searchStr = `${reading.readingValue} ${reading.unit} ${reading.remarks || ''} ${isWarning ? 'cảnh báo nguy hiểm' : ''}`.toLowerCase();
    return searchStr.includes(term);
  });

  return (
    <div className="mt-2 min-h-[300px]">
      {loading ? (
        <div className="flex justify-center items-center h-40">
          <span className="text-neutral-400">Đang tải...</span>
        </div>
      ) : sortedReadings.length === 0 ? (
        <div className="flex flex-col items-center justify-center text-neutral-400 py-12 bg-neutral-50 rounded-2xl border border-neutral-100">
          <i className="ph ph-gauge text-5xl mb-3 text-neutral-300"></i>
          <p className="font-medium text-neutral-500">Chưa có chỉ số hoạt động nào</p>
        </div>
      ) : (
        <div className="flex flex-col h-full">
          <Input
            placeholder="Tìm kiếm theo chỉ số, đơn vị, hoặc ghi chú..."
            prefix={<SearchOutlined className="text-neutral-400" />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            className="mb-6 h-10 rounded-xl bg-neutral-50 hover:bg-neutral-100 border-neutral-200 w-full sm:max-w-md transition-colors"
          />
          <div className="max-h-[400px] overflow-y-auto px-2 pb-4 custom-scrollbar">
            <Timeline
              items={filteredReadings.map((reading) => {
                const isWarning = reading.remarks?.toLowerCase().match(/(nguy hiểm|cảnh báo|vượt ngưỡng|bất thường|quá cao|nóng|lỗi|danger|warning|high)/);
                
                return {
                  color: isWarning ? 'red' : 'blue',
                  children: (
                    <div className={`mb-5 rounded-xl p-5 border transition-colors shadow-sm w-full lg:w-3/4 xl:w-2/3 ${isWarning ? 'bg-red-50/50 border-red-100 hover:border-red-200' : 'bg-neutral-50 border-neutral-200 hover:border-neutral-300'}`}>
                      <div className="flex items-center flex-wrap gap-3 mb-3">
                        <span className="font-black text-neutral-900 text-lg">
                          {new Intl.NumberFormat('vi-VN').format(reading.readingValue)} <span className="text-sm text-neutral-500 font-bold">{reading.unit}</span>
                        </span>
                        {isWarning && (
                          <Tag color="error" className="rounded font-bold border-0 text-[10px] m-0 flex items-center gap-1 tracking-widest px-2">
                            <i className="ph-fill ph-warning"></i> CẢNH BÁO
                          </Tag>
                        )}
                        <span className="text-xs text-neutral-500 ml-auto flex items-center gap-1.5 font-semibold bg-white px-3 py-1.5 rounded-lg border border-neutral-100 shadow-sm">
                          <i className="ph ph-clock text-primary"></i> {dayjs(reading.readingDate).format('HH:mm DD/MM/YYYY')}
                        </span>
                      </div>
                      {reading.remarks && (
                        <p className={`text-base mb-3 ${isWarning ? 'font-bold text-red-700' : 'font-medium text-neutral-800'}`}>
                          {reading.remarks}
                        </p>
                      )}
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-neutral-200 flex items-center justify-center text-neutral-500">
                          <i className="ph-fill ph-user text-xs"></i>
                        </span> 
                        <span className="text-sm font-medium text-neutral-600">Người ghi nhận</span>
                      </div>
                    </div>
                  )
                };
              })}
            />
            {filteredReadings.length === 0 && (
              <div className="text-center py-8 text-neutral-400">Không tìm thấy kết quả phù hợp.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
