import React from 'react';
import { Table, Tag, Input, Select, Button, Spin } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
dayjs.extend(utc);

import { useCalendarStore } from '../../work-orders/store/useCalendarStore';

export const MaintenanceList: React.FC = () => {
  const { events, isLoading, filters, setFilters, fetchEvents, currentDate, setCurrentDate } = useCalendarStore();

  React.useEffect(() => {
    const startDate = currentDate.startOf('month').startOf('week').toISOString();
    const endDate = currentDate.endOf('month').endOf('week').toISOString();
    fetchEvents(startDate, endDate);
  }, [currentDate, filters, fetchEvents]);

  const columns = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (text: string) => <span className="font-semibold">{text}</span>,
    },
    {
      title: 'Asset',
      dataIndex: 'assetName',
      key: 'assetName',
    },
    {
      title: 'Target Date',
      dataIndex: 'eventDate',
      key: 'eventDate',
      render: (date: string) => dayjs.utc(date).local().format('YYYY-MM-DD HH:mm'),
      sorter: (a: any, b: any) => dayjs(a.eventDate).valueOf() - dayjs(b.eventDate).valueOf(),
    },
    {
      title: 'Type',
      dataIndex: 'eventType',
      key: 'eventType',
      render: (type: string) => (
        <Tag color={type === 'PM_PLAN' ? 'blue' : 'purple'}>
          {type === 'PM_PLAN' ? 'PM Plan' : 'Work Order'}
        </Tag>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        let color = 'default';
        if (status === 'COMPLETED') color = 'success';
        else if (status === 'IN_PROGRESS') color = 'processing';
        else if (status === 'SCHEDULED') color = 'warning';
        return <Tag color={color}>{status}</Tag>;
      },
    },
  ];

  return (
    <div className="flex flex-col h-full bg-white border border-neutral-200 rounded-3xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="p-4 border-b border-neutral-200 flex flex-wrap justify-between items-center gap-4 bg-white shrink-0">
        <div className="flex flex-wrap items-center gap-4">
          <h3 className="font-bold text-lg text-neutral-800 m-0">
            Events for {currentDate.format('MMMM YYYY')}
          </h3>
          <div className="flex gap-2">
            <Button onClick={() => setCurrentDate(currentDate.subtract(1, 'month'))}>Previous Month</Button>
            <Button onClick={() => setCurrentDate(dayjs())}>Today</Button>
            <Button onClick={() => setCurrentDate(currentDate.add(1, 'month'))}>Next Month</Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Input 
            placeholder="Asset ID" 
            allowClear 
            className="w-32"
            value={filters.assetId} 
            onChange={(e) => setFilters({ assetId: e.target.value || undefined })}
          />
          <Input 
            placeholder="Category ID" 
            allowClear 
            className="w-32"
            value={filters.categoryId} 
            onChange={(e) => setFilters({ categoryId: e.target.value || undefined })}
          />
          <Select
            placeholder="Filter by Status"
            allowClear
            className="w-40"
            value={filters.status}
            onChange={(val) => setFilters({ status: val })}
            options={[
              { label: 'Created', value: 'CREATED' },
              { label: 'In Progress', value: 'IN_PROGRESS' },
              { label: 'Completed', value: 'COMPLETED' },
              { label: 'Scheduled (PM)', value: 'SCHEDULED' }
            ]}
          />
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4 relative">
        {isLoading && (
          <div className="absolute inset-0 bg-white/50 backdrop-blur-[1px] z-10 flex justify-center items-center">
            <Spin size="large" />
          </div>
        )}
        <Table 
          dataSource={events} 
          columns={columns} 
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      </div>
    </div>
  );
};
