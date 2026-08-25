import React, { useEffect, useState } from 'react';
import { Calendar, Badge, Spin, Select, Drawer, Descriptions, Tag, Button, Input, message } from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
dayjs.extend(utc);

import { useCalendarStore } from '../../work-orders/store/useCalendarStore';
import type { CalendarEvent } from '../../work-orders/store/useCalendarStore';
import { workOrderApi } from '../../work-orders/api/workOrderApi';

export const MaintenanceCalendar: React.FC = () => {
  const { events, isLoading, error, currentDate, mode, filters, fetchEvents, setCurrentDate, setMode, setFilters } = useCalendarStore();
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [eventDetail, setEventDetail] = useState<any>(null);
  const [listDate, setListDate] = useState<Dayjs | null>(null);
  const [listMode, setListMode] = useState<'date' | 'month' | null>(null);

  useEffect(() => {
    const startDate = mode === 'year'
      ? currentDate.startOf('year').toISOString()
      : currentDate.startOf('month').startOf('week').toISOString();
    const endDate = mode === 'year'
      ? currentDate.endOf('year').toISOString()
      : currentDate.endOf('month').endOf('week').toISOString();
    fetchEvents(startDate, endDate);
  }, [currentDate, mode, filters, fetchEvents]);

  useEffect(() => {
    if (error) {
      message.error(error);
    }
  }, [error]);

  const onPanelChange = (date: Dayjs, newMode: 'month' | 'year') => {
    setCurrentDate(date);
    setMode(newMode);
  };

  const handleEventClick = async (event: CalendarEvent, e: React.MouseEvent) => {
    e.stopPropagation();
    // Do not clear listDate and listMode so we can go back
    setSelectedEvent(event);
    setEventDetail(null);
    setDrawerVisible(true);
    
    if (event.eventType === 'WORK_ORDER') {
      setDrawerLoading(true);
      try {
        const response = await workOrderApi.getWorkOrder(event.id);
        if (response.data.success) {
          setEventDetail(response.data.data);
        }
      } catch (error) {
        console.error('Failed to fetch work order detail', error);
      } finally {
        setDrawerLoading(false);
      }
    } else {
      setEventDetail(null); // For PM_PLAN projections, we might not have a full detail endpoint yet
    }
  };

  const handleCellDoubleClick = (value: Dayjs, type: 'date' | 'month', e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedEvent(null);
    setEventDetail(null);
    setListDate(value);
    setListMode(type);
    setDrawerVisible(true);
  };

  const getListData = (value: Dayjs) => {
    return events.filter(e => {
      const eventDate = dayjs.utc(e.eventDate).local();
      return eventDate.isSame(value, 'day');
    }).filter(e => {
      if (filters.status && e.status !== filters.status) return false;
      return true;
    });
  };

  const dateCellRender = (value: Dayjs) => {
    const listData = getListData(value);
    const displayData = listData.slice(0, 3);
    const hasMore = listData.length > 3;

    return (
      <div 
        className="w-full h-full" 
        onDoubleClick={(e) => handleCellDoubleClick(value, 'date', e)}
      >
        <ul className="m-0 p-0 list-none overflow-hidden text-left w-full">
          {displayData.map((item) => {
            let color = 'default';
            if (item.status === 'COMPLETED') color = 'success';
            else if (item.status === 'IN_PROGRESS') color = 'processing';
            else if (item.status === 'SCHEDULED') color = 'warning';
            else if (item.status === 'CREATED') color = 'default';
            
            return (
              <li key={item.id} className="mb-1 pointer-events-none">
                <div className={`text-[10px] sm:text-xs truncate px-1 rounded-sm bg-neutral-50 border border-neutral-100 flex items-center gap-1`}>
                  <Badge status={color as any} /> 
                  <span className="font-semibold text-neutral-700">{item.title}</span>
                  {item.assetName && <span className="text-[9px] text-neutral-400 ml-1">[{item.assetName}]</span>}
                </div>
              </li>
            );
          })}
          {hasMore && (
            <li className="text-center text-neutral-400 font-bold text-[10px] leading-none mt-1 pointer-events-none">...</li>
          )}
        </ul>
      </div>
    );
  };

  const getMonthData = (value: Dayjs) => {
    return events.filter(e => {
      const eventDate = dayjs.utc(e.eventDate).local();
      return eventDate.isSame(value, 'month');
    }).filter(e => {
      if (filters.status && e.status !== filters.status) return false;
      return true;
    });
  };

  const monthCellRender = (value: Dayjs) => {
    const listData = getMonthData(value);
    if (listData.length === 0) {
      return (
        <div 
          className="w-full h-full" 
          onDoubleClick={(e) => handleCellDoubleClick(value, 'month', e)}
        />
      );
    }
    return (
      <div 
        className="w-full h-full flex flex-col items-center justify-center pt-2"
        onDoubleClick={(e) => handleCellDoubleClick(value, 'month', e)}
      >
        <Badge count={listData.length} style={{ backgroundColor: '#1677FF' }} />
        <div className="text-xs text-neutral-500 mt-1 font-medium pointer-events-none">Sự kiện</div>
      </div>
    );
  };

  const cellRender = (current: Dayjs, info: any) => {
    if (info.type === 'date') return dateCellRender(current);
    if (info.type === 'month') return monthCellRender(current);
    return info.originNode;
  };

  const renderDrawerContent = () => {
    if (drawerLoading) {
      return <div className="flex justify-center py-10"><Spin /></div>;
    }

    if (selectedEvent) {
      const handleBack = () => {
        setSelectedEvent(null);
        setEventDetail(null);
      };

      const BackButton = () => (
        <Button type="link" onClick={handleBack} style={{ paddingLeft: 0, marginBottom: 16 }}>
          &larr; Quay lại danh sách
        </Button>
      );

      if (selectedEvent.eventType === 'PM_PLAN') {
        return (
          <>
            <BackButton />
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Plan Name">{selectedEvent.title}</Descriptions.Item>
              <Descriptions.Item label="Asset">{selectedEvent.assetName}</Descriptions.Item>
              <Descriptions.Item label="Expected Date">{dayjs(selectedEvent.eventDate).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="Estimated Duration">{selectedEvent.originalData?.estimatedDurationMinutes ? `${selectedEvent.originalData.estimatedDurationMinutes} phút` : '-'}</Descriptions.Item>
              <Descriptions.Item label="Assignee">{selectedEvent.originalData?.assignee?.fullName || selectedEvent.originalData?.assignee?.username || 'Chưa phân công'}</Descriptions.Item>
              {selectedEvent.originalData?.materials && selectedEvent.originalData.materials.length > 0 && (
                <Descriptions.Item label="Materials">
                  <div className="space-y-1">
                    {selectedEvent.originalData.materials.map((m: any) => (
                      <div key={m.id} className="text-xs">
                        • {m.sparePartName} <span className="text-neutral-400">({m.sparePartId?.substring(0, 8)})</span>: <span className="font-bold">x{m.quantity}</span>
                      </div>
                    ))}
                  </div>
                </Descriptions.Item>
              )}
              <Descriptions.Item label="Status"><Tag color="warning">Scheduled</Tag></Descriptions.Item>
            </Descriptions>
          </>
        );
      }

      if (eventDetail) {
        return (
          <>
            <BackButton />
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="Work Order Title">{eventDetail.title}</Descriptions.Item>
              <Descriptions.Item label="Description">{eventDetail.description || '-'}</Descriptions.Item>
              <Descriptions.Item label="Asset">{eventDetail.asset?.name}</Descriptions.Item>
              <Descriptions.Item label="Priority">
                <Tag color={eventDetail.priority === 'HIGH' ? 'red' : eventDetail.priority === 'MEDIUM' ? 'orange' : 'blue'}>
                  {eventDetail.priority}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Status">{eventDetail.status}</Descriptions.Item>
              <Descriptions.Item label="Deadline">{dayjs(eventDetail.deadline).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
              <Descriptions.Item label="Requested By">{eventDetail.creator?.fullName || eventDetail.creator?.username || 'Hệ thống'}</Descriptions.Item>
              <Descriptions.Item label="Assignee">{eventDetail.assignee?.fullName || eventDetail.assignee?.username || 'Chưa phân công'}</Descriptions.Item>
              <Descriptions.Item label="Estimated Duration">{eventDetail.estimatedDurationMinutes ? `${eventDetail.estimatedDurationMinutes} phút` : '-'}</Descriptions.Item>
              {eventDetail.materials && eventDetail.materials.length > 0 && (
                <Descriptions.Item label="Materials">
                  <div className="space-y-1">
                    {eventDetail.materials.map((m: any) => (
                      <div key={m.id} className="text-xs">
                        • {m.sparePart?.name} <span className="text-neutral-400">({m.sparePart?.partNumber})</span>: <span className="font-bold">x{m.quantity}</span>
                      </div>
                    ))}
                  </div>
                </Descriptions.Item>
              )}
            </Descriptions>
          </>
        );
      }

      return null;
    }

    if (listDate && listMode) {
      const data = listMode === 'date' ? getListData(listDate) : getMonthData(listDate);
      if (data.length === 0) {
        return <div className="text-center text-neutral-500 mt-10">Không có sự kiện nào</div>;
      }
      return (
        <div className="flex flex-col gap-3">
          {data.map(item => (
            <div 
              key={item.id} 
              className="p-3 border border-neutral-200 rounded-lg hover:border-blue-400 cursor-pointer transition-colors shadow-sm bg-neutral-50"
              onClick={(e) => handleEventClick(item, e)}
            >
              <div className="font-semibold text-neutral-800">{item.title}</div>
              <div className="text-xs text-neutral-500 mt-1 mb-2">Tài sản: {item.assetName || 'N/A'}</div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-neutral-400">{dayjs(item.eventDate).format('YYYY-MM-DD HH:mm')}</span>
                <Tag color={item.status === 'COMPLETED' ? 'success' : item.status === 'SCHEDULED' ? 'warning' : item.status === 'IN_PROGRESS' ? 'processing' : 'default'} className="m-0">
                  {item.status}
                </Tag>
              </div>
            </div>
          ))}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="flex flex-col h-full bg-white border border-neutral-200 rounded-3xl shadow-[0_4px_20px_rgba(0,0,0,0.03)] overflow-hidden">
      <div className="p-4 border-b border-neutral-200 flex flex-wrap justify-between items-center gap-4 bg-white shrink-0">
        <h3 className="font-bold text-lg text-neutral-800 m-0">Maintenance Schedule</h3>
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
        <Calendar 
          mode={mode}
          value={currentDate} 
          onPanelChange={onPanelChange} 
          onChange={(date) => setCurrentDate(date)}
          cellRender={cellRender} 
          className="maintenance-calendar"
        />
      </div>

      <Drawer
        title={
          listDate 
            ? `Danh sách sự kiện - ${listDate.format(listMode === 'date' ? 'DD/MM/YYYY' : 'MM/YYYY')}` 
            : "Chi tiết sự kiện"
        }
        placement="right"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={400}
      >
        {renderDrawerContent()}
        <div className="mt-6 flex justify-end">
           {selectedEvent?.eventType === 'WORK_ORDER' && (
              <Button type="primary" onClick={() => window.open('/work-orders', '_self')}>
                Go to Work Orders
              </Button>
           )}
        </div>
      </Drawer>
    </div>
  );
};
