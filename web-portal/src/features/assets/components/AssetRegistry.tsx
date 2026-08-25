import React, { useEffect, useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Button, Modal, Form, Input, Select, DatePicker, message, Popconfirm, Popover, Tag, InputNumber, Tabs, TreeSelect, Upload } from 'antd';
import * as XLSX from 'xlsx';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, UploadOutlined } from '@ant-design/icons';
import { useAssetRegistryStore, type Asset } from '../store/useAssetRegistryStore';
import { useAssetStore, type Location } from '../store/useAssetStore';
import { QRCodeCanvas } from 'qrcode.react';
import dayjs from 'dayjs';
import CreateWorkOrderDrawer from '../../work-orders/components/CreateWorkOrderDrawer';
import { MeterReadingPanel } from './MeterReadingPanel';
import { workOrderApi } from '../../work-orders/api/workOrderApi';

const { Option } = Select;

export const AssetRegistry: React.FC = () => {
  const { treeData, fetchAssetTree, createAsset, updateAsset, deleteAsset, importAssets, exportAssets } = useAssetRegistryStore();
  const { categories, fetchCategories, locations, fetchLocations, templates, fetchTemplates } = useAssetStore();

  const [treeCollapsed, setTreeCollapsed] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingAsset, setEditingAsset] = useState<Asset | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(() => {
    try {
      const saved = localStorage.getItem('assetTreeExpandedNodes');
      return saved ? new Set(JSON.parse(saved)) : new Set();
    } catch {
      return new Set();
    }
  });
  const [form] = Form.useForm();

  const [isMoveModalVisible, setIsMoveModalVisible] = useState(false);
  const [movingLocationId, setMovingLocationId] = useState<string | undefined>(undefined);
  const [movingSubmitting, setMovingSubmitting] = useState(false);
  const [isImportVisible, setIsImportVisible] = useState(false);
  const [isWorkOrderModalVisible, setIsWorkOrderModalVisible] = useState(false);

  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [historySearch, setHistorySearch] = useState('');

  useEffect(() => {
    if (selectedAsset) {
      const fetchHistory = async () => {
        setHistoryLoading(true);
        try {
          const res = await workOrderApi.getCalendarEvents(
            dayjs().subtract(5, 'year').toISOString(),
            dayjs().add(1, 'year').toISOString(),
            selectedAsset.id
          );
          if (res.data.success) {
            const completedWos = res.data.data
              .filter((e: any) => e.eventType === 'WORK_ORDER' && (e.status === 'COMPLETED' || e.status === 'CANCELED'))
              .map((e: any) => e.originalData)
              .sort((a: any, b: any) => new Date(b.updatedAt || b.createdAt).getTime() - new Date(a.updatedAt || a.createdAt).getTime());
            setHistoryData(completedWos);
          }
        } catch (error) {
          console.error('Failed to fetch asset history', error);
        } finally {
          setHistoryLoading(false);
        }
      };
      fetchHistory();
    }
  }, [selectedAsset]);

  const handleMoveOk = async () => {
    if (!selectedAsset) return;
    if (movingLocationId === selectedAsset.locationId) {
      setIsMoveModalVisible(false);
      setMovingLocationId(undefined);
      return;
    }
    try {
      setMovingSubmitting(true);
      await updateAsset(selectedAsset.id, {
        name: selectedAsset.name,
        categoryId: selectedAsset.categoryId || undefined,
        hierarchyTemplateId: selectedAsset.hierarchyTemplateId || undefined,
        serialNumber: selectedAsset.serialNumber || undefined,
        model: selectedAsset.model || undefined,
        manufacturer: selectedAsset.manufacturer || undefined,
        purchaseDate: selectedAsset.purchaseDate || undefined,
        value: selectedAsset.value || undefined,
        status: selectedAsset.status,
        isActive: selectedAsset.isActive,
        locationId: movingLocationId
      });
      message.success('Di chuyển tài sản thành công');
      setIsMoveModalVisible(false);
      setMovingLocationId(undefined);
      fetchAssetTree(debouncedSearch, statusFilter || '', categoryFilter || '');
    } catch (error: any) {
      if (error.response?.data?.error) {
        message.error(error.response.data.error);
      } else {
        message.error('Lỗi khi di chuyển tài sản');
      }
    } finally {
      setMovingSubmitting(false);
    }
  };

  useEffect(() => {
    // fetchAssets is not defined, assuming it was meant to be fetchAssetTree/others
    fetchCategories();
    fetchLocations();
    fetchTemplates();
  }, [fetchCategories, fetchLocations, fetchTemplates]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchText), 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  useEffect(() => {
    fetchAssetTree(debouncedSearch, statusFilter || '', categoryFilter || '');
  }, [fetchAssetTree, debouncedSearch, statusFilter, categoryFilter]);

  useEffect(() => {
    if (selectedAsset) {
      sessionStorage.setItem('selectedAssetId', selectedAsset.id);
    }
  }, [selectedAsset]);

  useEffect(() => {
    if (!treeData) return;

    const savedId = sessionStorage.getItem('selectedAssetId');
    let targetId = selectedAsset?.id || savedId;

    if (targetId) {
      let found = treeData.unassignedAssets?.find((a: Asset) => a.id === targetId);
      if (!found) {
        const findInTree = (nodes: any[]): Asset | undefined => {
          for (const node of nodes) {
            const asset = node.assets?.find((a: Asset) => a.id === targetId);
            if (asset) return asset;
            if (node.children) {
              const childAsset = findInTree(node.children);
              if (childAsset) return childAsset;
            }
          }
          return undefined;
        };
        found = findInTree(treeData.locations || []);
      }
      if (found) {
        if (!selectedAsset || selectedAsset.id !== found.id) {
          setSelectedAsset(found);
        }
        return;
      }
    }

    // Fallback
    if (treeData.locations?.length > 0 && treeData.locations[0].assets?.length > 0) {
      setSelectedAsset(treeData.locations[0].assets[0]);
    } else if (treeData.unassignedAssets?.length > 0) {
      setSelectedAsset(treeData.unassignedAssets[0]);
    } else {
      setSelectedAsset(null);
    }
  }, [treeData]);

  const handleAdd = () => {
    setEditingAsset(null);
    form.resetFields();
    setIsModalVisible(true);
  };

  const downloadTemplate = async () => {
    try {
      const csvData = await exportAssets();
      const workbook = XLSX.read(csvData, { type: 'string', raw: true });
      XLSX.writeFile(workbook, 'Assets_Template.xlsx');
      message.success('Tải mẫu thành công');
    } catch (error) {
      message.error('Lỗi khi tải mẫu');
    }
  };

  const [isPrintingAll, setIsPrintingAll] = useState(false);
  const [assetsToPrint, setAssetsToPrint] = useState<Asset[]>([]);
  const [isBulkFilterVisible, setIsBulkFilterVisible] = useState(false);
  const [bulkStatusFilter, setBulkStatusFilter] = useState<string | null>(null);
  const [bulkCategoryFilter, setBulkCategoryFilter] = useState<string | null>(null);
  const [bulkLocationFilter, setBulkLocationFilter] = useState<string | null>(null);
  const [bulkTemplateFilter, setBulkTemplateFilter] = useState<string | null>(null);

  const getFilteredAssets = (): Asset[] => {
    if (!treeData) return [];
    let all: Asset[] = [];
    if (treeData.unassignedAssets) {
      all = [...all, ...treeData.unassignedAssets];
    }
    const traverse = (nodes: any[]) => {
      nodes.forEach(node => {
        if (node.assets) all = [...all, ...node.assets];
        if (node.children) traverse(node.children);
      });
    };
    if (treeData.locations) traverse(treeData.locations);

    if (bulkStatusFilter) all = all.filter(a => a.status === bulkStatusFilter);
    if (bulkCategoryFilter) all = all.filter(a => a.categoryId === bulkCategoryFilter);
    if (bulkLocationFilter) all = all.filter(a => a.locationId === bulkLocationFilter);
    if (bulkTemplateFilter) all = all.filter(a => a.hierarchyTemplateId === bulkTemplateFilter);

    return all;
  };

  const executeExportData = () => {
    const all = getFilteredAssets();
    if (all.length === 0) {
      message.warning('Không tìm thấy tài sản nào phù hợp với bộ lọc.');
      return;
    }

    const header = [
      "Name", "Category", "Template", "Serial Number", "Model",
      "Manufacturer", "Purchase Date", "Value", "Status", "Location",
      "QR Code", "IsActive"
    ];

    const rows = all.map(a => [
      a.name || '',
      a.categoryName || '',
      a.hierarchyTemplateName || '',
      a.serialNumber || '',
      a.model || '',
      a.manufacturer || '',
      a.purchaseDate ? dayjs(a.purchaseDate).format('YYYY-MM-DD') : '',
      a.value !== null ? String(a.value) : '',
      a.status || '',
      a.locationName || '',
      a.qrCode || '',
      a.isActive ? 'true' : 'false'
    ]);

    const worksheet = XLSX.utils.aoa_to_sheet([header, ...rows]);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Assets');
    XLSX.writeFile(workbook, `Assets_Export_${dayjs().format('YYYYMMDD')}.xlsx`);
    message.success(`Xuất thành công ${all.length} tài sản`);
    setIsBulkFilterVisible(false);
  };

  const executePrintAllQR = () => {
    const all = getFilteredAssets();
    if (all.length === 0) {
      message.warning('Không tìm thấy tài sản nào phù hợp với bộ lọc.');
      return;
    }

    setAssetsToPrint(all);
    setIsBulkFilterVisible(false);
    setIsPrintingAll(true);
    message.loading({ content: `Đang chuẩn bị trang in cho ${all.length} mã QR...`, key: 'print', duration: 0 });

    setTimeout(() => {
      window.print();
      setIsPrintingAll(false);
      message.destroy('print');
    }, 1500);
  };

  const handleEdit = () => {
    if (!selectedAsset) return;
    setEditingAsset(selectedAsset);
    form.setFieldsValue({
      ...selectedAsset,
      purchaseDate: selectedAsset.purchaseDate ? dayjs(selectedAsset.purchaseDate) : null,
      hierarchyTemplateId: selectedAsset.hierarchyTemplateId || undefined,
    });
    setIsModalVisible(true);
  };

  const handleDelete = async () => {
    if (!selectedAsset) return;
    try {
      await deleteAsset(selectedAsset.id);
      message.success('Đã xóa tài sản');
      setSelectedAsset(null);
      fetchAssetTree(debouncedSearch, statusFilter || '', categoryFilter || '');
    } catch (error: any) {
      message.error('Lỗi khi xóa tài sản');
    }
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const payload = {
        ...values,
        purchaseDate: values.purchaseDate ? values.purchaseDate.format('YYYY-MM-DD') : null,
      };

      if (editingAsset) {
        await updateAsset(editingAsset.id, payload);
        message.success('Cập nhật tài sản thành công');
      } else {
        await createAsset(payload);
        message.success('Tạo tài sản thành công');
      }
      setIsModalVisible(false);
      fetchAssetTree(debouncedSearch, statusFilter || '', categoryFilter || '');
    } catch (error: any) {
      if (error.response?.data?.error) {
        message.error(error.response.data.error);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const formatLtree = (s: string) => {
    if (!s) return '';
    let normalized = s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    let ltree = normalized.replace(/[^a-zA-Z0-9.]/g, '_');
    ltree = ltree.replace(/_+/g, '_').replace(/\.+/g, '.');
    ltree = ltree.replace(/^[_.]+|[_.]+$/g, '');
    return ltree;
  };

  const getFullPath = (l: Location): string => {
    return l.parentId ? `${l.parentId}.${formatLtree(l.name)}` : formatLtree(l.name);
  };

  const buildLocationTree = (parentId: string | null = null): any[] => {
    return locations
      .filter(l => (parentId ? l.parentId === parentId : !l.parentId) && l.isActive)
      .map(l => ({
        value: l.id,
        title: l.name,
        disabled: selectedAsset ? l.id === selectedAsset.locationId : false,
        children: buildLocationTree(getFullPath(l)),
      }));
  };
  const locationTreeData = useMemo(() => buildLocationTree(), [locations, selectedAsset]);

  const toggleNode = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(expandedNodes);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpandedNodes(next);
    localStorage.setItem('assetTreeExpandedNodes', JSON.stringify(Array.from(next)));
  };

  const renderTreeNode = (node: any, depth = 0) => {
    // Auto-expand if searching and match found inside
    const isExpanded = expandedNodes.has(node.id) || (searchText.length > 0 && ((node.children && node.children.length > 0) || (node.assets && node.assets.length > 0)));
    const hasChildren = (node.children && node.children.length > 0) || (node.assets && node.assets.length > 0);

    return (
      <div key={node.id} className="tree-node mt-1">
        <div className={`group flex items-center gap-1.5 p-1.5 hover:bg-neutral-100 rounded cursor-pointer font-medium transition-colors ${!node.isActive ? 'text-neutral-400 italic bg-neutral-50/50' : 'text-neutral-700'}`} onClick={(e) => toggleNode(node.id, e)}>
          <i className={`ph-fill ph-caret-down text-xs transition-transform ${isExpanded ? '' : '-rotate-90'} ${!hasChildren ? 'invisible' : ''} ${!node.isActive ? 'text-neutral-300' : 'text-neutral-400'}`}></i>
          {depth === 0 ? <i className={`ph-fill ph-buildings text-sm ${!node.isActive ? 'text-neutral-300' : 'text-neutral-400'}`}></i> : <i className={`ph-fill ph-factory text-sm ${!node.isActive ? 'text-neutral-300' : 'text-neutral-400'}`}></i>}
          <span className="truncate text-sm flex items-center gap-2">
            {node.name}
            {!node.isActive && (
              <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-red-100 text-red-600 not-italic">
                Đã khóa
              </span>
            )}
          </span>
        </div>

        {isExpanded && hasChildren && (
          <div className="ml-5 border-l border-neutral-200 pl-1.5 mt-0.5 space-y-0.5">
            {node.children && node.children.map((child: any) => renderTreeNode(child, depth + 1))}
            {node.assets && node.assets.map((asset: any) => (
              <div
                key={asset.id}
                onClick={(e) => { e.stopPropagation(); setSelectedAsset(asset); }}
                className={`group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-all ${selectedAsset?.id === asset.id ? 'bg-primary-50 text-primary font-semibold relative' : 'text-neutral-700 hover:bg-neutral-100'}`}
              >
                {selectedAsset?.id === asset.id && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-primary rounded-r"></span>}
                <i className={`ph-fill ph-engine text-base ${selectedAsset?.id === asset.id ? '' : 'text-neutral-400'}`}></i>
                <span className="flex-1 truncate text-[13px]">{asset.name}</span>
                <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${asset.status === 'OPERATIONAL' ? 'bg-green-500' : asset.status === 'MAINTENANCE' ? 'bg-orange-500' : 'bg-red-500'}`} title={asset.status}></span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const handlePrintQR = () => {
    if (!selectedAsset) return;
    const canvas = document.querySelector('.qr-canvas-container canvas') as HTMLCanvasElement;
    if (!canvas) {
      message.error('Không tìm thấy mã QR để in');
      return;
    }
    const qrImage = canvas.toDataURL('image/png');
    const printWindow = window.open('', '_blank', 'width=400,height=400');
    if (!printWindow) {
      message.error('Vui lòng cho phép mở popup để in');
      return;
    }
    printWindow.document.write(`
      <html>
        <head>
          <title>In Mã Định Danh - ${selectedAsset.name}</title>
          <style>
            @page { margin: 0; size: 50mm 50mm; }
            body { 
              margin: 0; 
              display: flex; 
              flex-direction: column;
              align-items: center; 
              justify-content: center; 
              height: 100vh;
              font-family: Arial, sans-serif;
              background-color: white;
            }
            .label {
               text-align: center;
               width: 46mm;
               height: 46mm;
               box-sizing: border-box;
               display: flex;
               flex-direction: column;
               align-items: center;
               justify-content: center;
               border: 1px solid #1f2937;
               padding: 2mm;
            }
            img { width: 26mm; height: 26mm; margin: 0 auto; }
            .name { font-size: 9px; margin: 2mm 0 0 0; font-weight: bold; color: #000; line-height: 1.2; text-align: center; max-height: 22px; overflow: hidden; }
            .code { font-size: 8px; margin: 1mm 0 0 0; font-weight: bold; font-family: monospace; color: #000; }
            .category { font-size: 6px; margin: 1mm 0 0 0; color: #4b5563; text-transform: uppercase; letter-spacing: 0.05em; }
          </style>
        </head>
        <body>
          <div class="label">
             <img src="${qrImage}" />
             <div class="name">${selectedAsset.name}</div>
             <div class="code">${selectedAsset.qrCode}</div>
             <div class="category">${selectedAsset.categoryName || 'N/A'}</div>
          </div>
          <script>
            window.onload = function() {
              setTimeout(function() {
                window.print();
                window.close();
              }, 250);
            };
          </script>
        </body>
      </html>
    `);
    printWindow.document.close();
  };

  return (
    <div className="flex-1 flex flex-col md:flex-row gap-4 md:gap-6 overflow-hidden h-full">
      {/* Left Pane: Asset List */}
      <div className={`${treeCollapsed ? 'hidden md:flex w-14 min-w-[3.5rem]' : 'w-full md:w-1/3 md:min-w-[320px] md:max-w-sm'} ${selectedAsset ? 'hidden md:flex' : 'flex'} bg-white border border-neutral-200 rounded-xl shadow-[0_2px_10px_rgba(0,0,0,0.02)] flex-col overflow-hidden transition-all duration-300 relative`}>

        {/* Full Header */}
        {!treeCollapsed && (
          <div className="p-3 border-b border-neutral-200 bg-white flex items-center justify-between z-10 shadow-sm shrink-0">
            <h2 className="font-bold text-neutral-800 text-sm flex items-center gap-2 whitespace-nowrap">
              <i className="ph-fill ph-list-tree text-primary"></i> Cây Tài Sản
            </h2>
            <div className="flex gap-1 shrink-0">
              <button onClick={handleAdd} className="w-7 h-7 rounded hover:bg-primary/10 hover:text-primary flex items-center justify-center text-neutral-500 transition-colors" title="Thêm tài sản mới"><PlusOutlined /></button>
              <button onClick={() => setIsImportVisible(true)} className="w-7 h-7 rounded hover:bg-primary/10 hover:text-primary flex items-center justify-center text-neutral-500 transition-colors" title="Nhập (Import)"><i className="ph ph-upload-simple"></i></button>
              <button onClick={() => setIsBulkFilterVisible(true)} className="w-7 h-7 rounded hover:bg-primary/10 hover:text-primary flex items-center justify-center text-neutral-500 transition-colors" title="Xuất/In (Export/Print)"><i className="ph ph-printer"></i></button>
              <Popover
                trigger="click"
                placement="bottomRight"
                title="Lọc Tài Sản"
                content={
                  <div className="w-64 space-y-4">
                    <div>
                      <div className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Trạng thái</div>
                      <Select className="w-full" allowClear placeholder="Tất cả trạng thái" value={statusFilter} onChange={setStatusFilter}>
                        <Option value="OPERATIONAL">Đang hoạt động</Option>
                        <Option value="MAINTENANCE">Bảo trì</Option>
                        <Option value="BROKEN">Hỏng hóc</Option>
                        <Option value="DECOMMISSIONED">Thanh lý</Option>
                        <Option value="RESERVED">Dự trữ</Option>
                      </Select>
                    </div>
                    <div>
                      <div className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Danh mục</div>
                      <Select className="w-full" allowClear placeholder="Tất cả danh mục" value={categoryFilter} onChange={setCategoryFilter}>
                        {categories.filter(c => c.isActive).map(c => <Option key={c.id} value={c.id}>{c.name}</Option>)}
                      </Select>
                    </div>
                    <div className="flex justify-end pt-2 border-t border-neutral-100">
                      <Button type="link" size="small" onClick={() => { setStatusFilter(null); setCategoryFilter(null); }}>Xóa lọc</Button>
                    </div>
                  </div>
                }
              >
                <button className={`w-7 h-7 rounded flex items-center justify-center transition-colors ${statusFilter || categoryFilter ? 'bg-primary text-white' : 'hover:bg-neutral-100 text-neutral-500'}`} title="Lọc tài sản">
                  <i className="ph ph-funnel"></i>
                </button>
              </Popover>
              <button className="w-7 h-7 rounded hover:bg-neutral-100 flex items-center justify-center text-neutral-500 transition-colors" onClick={() => setTreeCollapsed(true)} title="Thu gọn"><i className="ph ph-caret-left"></i></button>
            </div>
          </div>
        )}

        {/* Mini Header (Collapsed) */}
        {treeCollapsed && (
          <div className="py-4 border-b border-neutral-200 bg-white flex flex-col items-center z-10 h-full cursor-pointer hover:bg-neutral-50 transition-colors shrink-0" onClick={() => setTreeCollapsed(false)} title="Mở rộng">
            <i className="ph-fill ph-list-tree text-primary text-xl"></i>
            <span className="text-[10px] font-bold text-neutral-400 uppercase tracking-widest mt-6" style={{ writingMode: 'vertical-rl', textOrientation: 'mixed' }}>CÂY TÀI SẢN</span>
          </div>
        )}

        {/* Content */}
        {!treeCollapsed && (
          <div className="flex-1 flex flex-col overflow-hidden">
            <div className="p-2 border-b border-neutral-100 bg-neutral-50/50 shrink-0">
              <Input
                placeholder="Tìm tên, mã Serial..."
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                className="h-9 rounded-lg"
                prefix={<SearchOutlined className="text-neutral-400 mr-1" />}
                variant="borderless"
                style={{ border: '1px solid #e5e7eb', backgroundColor: 'white' }}
              />
            </div>
            <div className="flex-1 overflow-y-auto p-2 text-sm select-none custom-scrollbar">
              {treeData?.locations?.map((l: any) => renderTreeNode(l))}

              {treeData?.unassignedAssets && treeData.unassignedAssets.length > 0 && (
                <div className="tree-node mt-3">
                  <div className="group flex items-center gap-1.5 p-1.5 text-neutral-700 font-medium opacity-80">
                    <i className="ph-fill ph-warning-circle text-neutral-400 text-sm"></i>
                    <span className="truncate italic text-sm">Chưa gán vị trí ({treeData.unassignedAssets.length})</span>
                  </div>
                  <div className="ml-5 border-l border-neutral-200 pl-1.5 mt-0.5 space-y-0.5">
                    {treeData.unassignedAssets.map((asset: any) => (
                      <div
                        key={asset.id}
                        onClick={(e) => { e.stopPropagation(); setSelectedAsset(asset); }}
                        className={`group flex items-center gap-2 px-2 py-1.5 rounded-md cursor-pointer transition-all ${selectedAsset?.id === asset.id ? 'bg-primary-50 text-primary font-semibold relative' : 'text-neutral-700 hover:bg-neutral-100'}`}
                      >
                        {selectedAsset?.id === asset.id && <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-primary rounded-r"></span>}
                        <i className={`ph-fill ph-engine text-base ${selectedAsset?.id === asset.id ? '' : 'text-neutral-400'}`}></i>
                        <span className="flex-1 truncate text-[13px]">{asset.name}</span>
                        <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${asset.status === 'OPERATIONAL' ? 'bg-green-500' : asset.status === 'MAINTENANCE' ? 'bg-orange-500' : 'bg-red-500'}`} title={asset.status}></span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(!treeData?.locations?.length && !treeData?.unassignedAssets?.length) && (
                <div className="text-center p-6 text-neutral-400 mt-4">
                  <i className="ph ph-magnifying-glass text-3xl mb-2"></i>
                  <p>Không tìm thấy tài sản nào</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Right Pane: Asset Details */}
      <div className={`flex-1 bg-white border border-neutral-200 rounded-xl flex-col overflow-hidden min-w-0 shadow-[0_2px_10px_rgba(0,0,0,0.02)] ${selectedAsset ? 'flex' : 'hidden md:flex'}`}>
        {selectedAsset ? (
          <>
            <div className="p-4 sm:p-6 border-b border-neutral-200 bg-white shrink-0 relative overflow-hidden">
              <div className="absolute top-0 right-0 -mr-16 -mt-16 w-[300px] h-[300px] rounded-full bg-gradient-to-bl from-info/10 via-primary-100/20 to-transparent blur-3xl opacity-50 pointer-events-none"></div>
              <div className="flex flex-wrap justify-between items-start gap-4 sm:gap-6 relative z-10">
                <div className="flex items-start gap-3 sm:gap-4 flex-auto min-w-0 md:min-w-[320px]">
                  <button
                    className="md:hidden mt-2 w-10 h-10 bg-neutral-100 hover:bg-neutral-200 rounded-xl flex items-center justify-center text-neutral-600 shrink-0 transition-colors"
                    onClick={() => setSelectedAsset(null)}
                  >
                    <i className="ph-bold ph-arrow-left"></i>
                  </button>
                  <div className="w-14 h-14 sm:w-16 sm:h-16 bg-primary-50 rounded-xl sm:rounded-2xl flex items-center justify-center text-primary text-2xl sm:text-3xl shrink-0 shadow-inner mt-1">
                    <i className="ph-fill ph-engine"></i>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] font-bold text-neutral-400 uppercase tracking-[0.18em] mb-1.5 hidden sm:block">CHI TIẾT TÀI SẢN</p>
                    <div className="flex items-center gap-3 flex-wrap mb-2.5">
                      <h2 className="text-2xl sm:text-3xl leading-tight font-black text-neutral-900 tracking-tight">{selectedAsset.name}</h2>
                      <div className="shrink-0 mt-1">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 ${selectedAsset.status === 'OPERATIONAL' ? 'bg-green-50 text-green-700' : 'bg-orange-50 text-orange-700'} text-[10px] font-bold uppercase tracking-wider rounded-md`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${selectedAsset.status === 'OPERATIONAL' ? 'bg-green-600' : 'bg-orange-600'}`}></span> {selectedAsset.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-xs flex-wrap">
                      <span className="flex items-center gap-1.5 font-mono text-neutral-500 bg-neutral-100 px-2.5 py-1 rounded-lg"><i className="ph ph-barcode text-sm"></i> {selectedAsset.serialNumber || 'N/A'}</span>
                      <span className="flex items-center gap-1.5 text-primary bg-primary/10 px-2.5 py-1 rounded-lg font-semibold"><i className="ph-fill ph-map-pin text-sm"></i> {selectedAsset.locationName || 'Chưa gán vị trí'}</span>
                      <span className="flex items-center gap-1.5 text-info bg-info/10 px-2.5 py-1 rounded-lg font-semibold"><i className="ph-fill ph-tree-structure text-sm"></i> {selectedAsset.hierarchyTemplateName || 'Chưa gán cấu trúc'}</span>
                    </div>
                    <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-4 text-xs mt-2 text-neutral-500">
                      <span className="flex items-center gap-1.5">
                        <i className="ph ph-clock-counter-clockwise"></i>
                        Được thêm vào lúc {dayjs(selectedAsset.createdAt).format('HH:mm DD/MM/YYYY')} {selectedAsset.createdByName ? `bởi ${selectedAsset.createdByName}` : ''}
                      </span>
                      {selectedAsset.updatedAt && selectedAsset.updatedAt !== selectedAsset.createdAt && (
                        <span className="flex items-center gap-1.5 sm:border-l sm:border-neutral-200 sm:pl-4">
                          <i className="ph ph-pencil-simple"></i>
                          Cập nhật lần cuối lúc {dayjs(selectedAsset.updatedAt).format('HH:mm DD/MM/YYYY')} {selectedAsset.updatedByName ? `bởi ${selectedAsset.updatedByName}` : ''}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2.5 shrink-0 flex-wrap">
                  <Popconfirm title="Xóa tài sản này?" onConfirm={handleDelete} okText="Xóa" cancelText="Hủy" okButtonProps={{ danger: true }}>
                    <button className="w-10 h-10 text-neutral-400 hover:text-danger hover:bg-red-50 rounded-xl flex items-center justify-center transition-colors">
                      <DeleteOutlined />
                    </button>
                  </Popconfirm>
                  <button onClick={() => { setMovingLocationId(selectedAsset.locationId || undefined); setIsMoveModalVisible(true); }} className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 font-semibold text-sm hover:bg-neutral-50 rounded-xl flex items-center gap-2 transition-colors h-10">
                    <i className="ph-bold ph-arrows-left-right text-lg"></i> Di chuyển
                  </button>
                  <button onClick={handleEdit} className="px-4 py-2 bg-white border border-neutral-300 text-neutral-700 font-semibold text-sm hover:bg-neutral-50 rounded-xl flex items-center gap-2 transition-colors h-10">
                    <EditOutlined className="text-lg" /> Sửa
                  </button>
                  <button
                    className="px-5 py-2 bg-primary text-white font-bold text-sm hover:bg-primary-600 rounded-xl flex items-center gap-2 transition-colors shadow-sm shadow-primary/30 h-10"
                    onClick={() => setIsWorkOrderModalVisible(true)}
                  >
                    <i className="ph-bold ph-plus text-lg"></i> Tạo Work Order
                  </button>
                </div>
              </div>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto bg-neutral-50/60 p-4 sm:p-6 custom-scrollbar">
              <div className="space-y-4 sm:space-y-6">

                {/* TOP CARDS: Location, Hierarchy, QR Code */}
                <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-6">
                  {/* Vị trí thực tế */}
                  <div className="bg-white border border-primary/10 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow min-w-0 flex flex-col justify-center">
                    <p className="text-[10px] font-bold text-primary/60 uppercase tracking-widest mb-3">Vị Trí Thực Tế (Location)</p>
                    {selectedAsset.locationName ? (
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary shrink-0 mt-0.5">
                          <i className="ph-fill ph-map-pin text-lg"></i>
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-neutral-900 text-base leading-tight truncate" title={selectedAsset.locationName.split('.').pop()}>{selectedAsset.locationName.split('.').pop()}</p>
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {selectedAsset.locationName.split('.').map((part, idx) => (
                              <span key={idx} className="text-[10px] bg-white border border-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded flex items-center gap-1.5 break-all sm:break-normal">
                                {idx > 0 && <span className="text-neutral-300 font-bold">&gt;</span>} {part}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm font-medium text-neutral-400 italic flex items-center gap-2"><i className="ph-fill ph-warning-circle"></i> Chưa thiết lập vị trí</p>
                    )}
                  </div>

                  {/* Cấu trúc mẫu */}
                  <div className="bg-white border border-info/10 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow min-w-0 flex flex-col justify-center">
                    <p className="text-[10px] font-bold text-info/60 uppercase tracking-widest mb-3">Cấu Trúc Mẫu (Hierarchy)</p>
                    {selectedAsset.hierarchyTemplateName ? (
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-info/10 flex items-center justify-center text-info shrink-0 mt-0.5">
                          <i className="ph-fill ph-tree-structure text-lg"></i>
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-neutral-900 text-base leading-tight truncate" title={selectedAsset.hierarchyTemplateName.split('.').pop()}>{selectedAsset.hierarchyTemplateName.split('.').pop()}</p>
                          <div className="flex flex-wrap gap-1.5 mt-2">
                            {selectedAsset.hierarchyTemplateName.split('.').map((part, idx) => (
                              <span key={idx} className="text-[10px] bg-white border border-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded flex items-center gap-1.5 break-all sm:break-normal">
                                {idx > 0 && <span className="text-neutral-300 font-bold">&gt;</span>} {part}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm font-medium text-neutral-400 italic flex items-center gap-2"><i className="ph-fill ph-warning-circle"></i> Chưa gán cấu trúc mẫu</p>
                    )}
                  </div>

                  {/* Mã Định Danh */}
                  <div className="bg-white border border-success/10 rounded-2xl p-5 shadow-sm hover:shadow-md transition-shadow min-w-0 flex flex-col justify-center">
                    <p className="text-[10px] font-bold text-success/60 uppercase tracking-widest mb-3">QR Code</p>
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="p-1 bg-white border border-neutral-100 rounded-lg shadow-sm qr-canvas-container shrink-0 mt-0.5">
                        <QRCodeCanvas
                          value={selectedAsset.qrCode}
                          size={48}
                          level="H"
                          includeMargin={false}
                        />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-bold text-neutral-900 text-base leading-tight truncate font-mono" title={selectedAsset.serialNumber || selectedAsset.qrCode}>
                          {selectedAsset.serialNumber || selectedAsset.qrCode.split('-')[0].toUpperCase()}
                        </p>
                        <div className="mt-2 w-full max-w-[120px]">
                          <button
                            className="w-full px-4 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-xs font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors flex items-center justify-center gap-2"
                            onClick={handlePrintQR}
                          >
                            <i className="ph ph-printer text-sm"></i> In QR
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* BOTTOM TABS */}
                <div className="bg-white border border-neutral-200 rounded-2xl shadow-sm overflow-hidden p-6">
                  <Tabs defaultActiveKey="info" className="asset-detail-tabs" items={[
                    {
                      key: 'info',
                      label: <span className="font-semibold flex items-center gap-2 px-2"><i className="ph-fill ph-info"></i> Thông Tin Chung</span>,
                      children: (
                        <div className="bg-neutral-50 border border-neutral-100 rounded-2xl p-6 shadow-inner mt-2">
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-y-8 gap-x-8">
                            <div className="min-w-0">
                              <p className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2 truncate" title="Danh mục phân loại">Danh mục phân loại</p>
                              <p className="font-semibold text-neutral-900 truncate text-base" title={selectedAsset.categoryName || '-'}>{selectedAsset.categoryName || '-'}</p>
                            </div>
                            <div className="min-w-0">
                              <p className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2 truncate" title="Nhà sản xuất">Nhà sản xuất</p>
                              <p className="font-semibold text-neutral-900 truncate text-base" title={selectedAsset.manufacturer || '-'}>{selectedAsset.manufacturer || '-'}</p>
                            </div>
                            <div className="min-w-0">
                              <p className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2 truncate" title="Model">Model</p>
                              <p className="font-semibold text-neutral-900 truncate text-base" title={selectedAsset.model || '-'}>{selectedAsset.model || '-'}</p>
                            </div>
                            <div className="min-w-0">
                              <p className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2 truncate" title="Ngày mua">Ngày mua</p>
                              <p className="font-semibold text-neutral-900 truncate text-base" title={selectedAsset.purchaseDate ? dayjs(selectedAsset.purchaseDate).format('DD/MM/YYYY') : '-'}>{selectedAsset.purchaseDate ? dayjs(selectedAsset.purchaseDate).format('DD/MM/YYYY') : '-'}</p>
                            </div>
                            <div className="min-w-0">
                              <p className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2 truncate" title="Giá trị">Giá trị</p>
                              <p className="font-semibold text-neutral-900 truncate text-base" title={selectedAsset.value ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(selectedAsset.value) : '-'}>{selectedAsset.value ? new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(selectedAsset.value) : '-'}</p>
                            </div>
                            <div className="min-w-0">
                              <p className="text-neutral-400 text-[10px] font-bold uppercase tracking-widest mb-2 truncate" title="Trạng thái Active">Trạng thái Active</p>
                              <div className="truncate"><Tag color={selectedAsset.isActive ? 'success' : 'error'} className="rounded font-bold border-0 text-xs px-2.5 py-0.5">{selectedAsset.isActive ? 'ACTIVE' : 'INACTIVE'}</Tag></div>
                            </div>
                          </div>
                        </div>
                      )
                    },
                    {
                      key: 'history',
                      label: <span className="font-semibold flex items-center gap-2 px-2"><i className="ph-fill ph-clock-counter-clockwise"></i> Lịch Sử Bảo Trì</span>,
                      children: (
                        <div className="mt-2 min-h-[300px]">
                          {historyLoading ? (
                            <div className="flex justify-center items-center h-40">
                              <span className="text-neutral-400">Đang tải...</span>
                            </div>
                          ) : historyData.length === 0 ? (
                            <div className="flex flex-col items-center justify-center text-neutral-400 py-12 bg-neutral-50 rounded-2xl border border-neutral-100">
                              <i className="ph ph-calendar-x text-5xl mb-3 text-neutral-300"></i>
                              <p className="font-medium text-neutral-500">Chưa có lịch sử bảo trì</p>
                            </div>
                          ) : (
                            <div className="flex flex-col h-full">
                              <Input
                                placeholder="Tìm kiếm theo tiêu đề phiếu hoặc mã phiếu..."
                                prefix={<SearchOutlined className="text-neutral-400" />}
                                value={historySearch}
                                onChange={e => setHistorySearch(e.target.value)}
                                className="mb-6 h-10 rounded-xl bg-neutral-50 hover:bg-neutral-100 border-neutral-200 w-full sm:max-w-md transition-colors"
                              />
                              <div className="max-h-[400px] overflow-y-auto px-2 pb-4 custom-scrollbar">
                                <div className="space-y-3">
                                  {historyData
                                    .filter((wo: any) =>
                                      wo.title?.toLowerCase().includes(historySearch.toLowerCase()) ||
                                      wo.id?.toLowerCase().includes(historySearch.toLowerCase())
                                    )
                                    .map((wo: any) => (
                                      <div key={wo.id} className="bg-white border border-neutral-200 rounded-2xl p-4 flex flex-col sm:flex-row sm:items-center gap-4 hover:border-primary/40 hover:shadow-md transition-all group">
                                        <div className="flex items-center gap-4 flex-1 min-w-0">
                                          <div className={`w-12 h-12 rounded-full flex items-center justify-center shrink-0 ${wo.status === 'COMPLETED' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'}`}>
                                            <i className={`ph-fill ${wo.status === 'COMPLETED' ? 'ph-check-circle' : 'ph-x-circle'} text-2xl`}></i>
                                          </div>
                                          <div className="min-w-0 flex-1">
                                            <div className="flex items-center gap-2 mb-1">
                                              <span className="font-black text-neutral-900 text-sm">#{wo.id.split('-')[0].toUpperCase()}</span>
                                              <Tag color={wo.status === 'COMPLETED' ? 'success' : 'error'} className="rounded font-bold border-0 text-[10px] m-0 tracking-widest px-1.5 py-0.5">{wo.status}</Tag>
                                            </div>
                                            <p className="font-bold text-neutral-800 text-base truncate" title={wo.title}>{wo.title}</p>
                                          </div>
                                        </div>

                                        <div className="flex flex-row sm:flex-col items-center sm:items-end justify-between sm:justify-center gap-2 shrink-0 border-t sm:border-t-0 sm:border-l border-neutral-100 pt-3 sm:pt-0 sm:pl-4">
                                          <div className="flex items-center gap-1.5 text-xs text-neutral-500 font-medium">
                                            <i className="ph ph-calendar-blank text-neutral-400"></i> {dayjs(wo.updatedAt || wo.createdAt).format('HH:mm DD/MM/YYYY')}
                                          </div>
                                          <div className="flex items-center gap-1.5 text-xs font-semibold text-neutral-600 bg-neutral-50 px-2.5 py-1.5 rounded-lg border border-neutral-100 shadow-sm">
                                            <span className="w-5 h-5 rounded-full bg-neutral-200 flex items-center justify-center text-neutral-500 overflow-hidden">
                                              <i className="ph-fill ph-user text-[10px]"></i>
                                            </span>
                                            {wo.assignee?.username || 'Chưa gán'}
                                          </div>
                                        </div>
                                      </div>
                                    ))}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    },
                    {
                      key: 'meterReadings',
                      label: <span className="font-semibold flex items-center gap-2 pr-2 pb-0.5"><i className="ph-fill ph-gauge"></i> Chỉ số hoạt động</span>,
                      children: <MeterReadingPanel assetId={selectedAsset.id} />
                    }
                  ]} />
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-neutral-400">
            <i className="ph-fill ph-engine text-6xl text-neutral-200 mb-4"></i>
            <p className="text-lg font-semibold text-neutral-500">Chưa chọn tài sản nào</p>
            <p className="text-sm">Vui lòng chọn một tài sản từ danh sách bên trái hoặc tạo mới.</p>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd} className="mt-4 rounded-xl">Tạo Tài Sản</Button>
          </div>
        )}
      </div>

      <Modal
        title={<h3 className="text-xl font-black text-neutral-900 m-0 pb-3 border-b border-neutral-100">{editingAsset ? "Cập Nhật Tài Sản" : "Thêm Tài Sản Mới"}</h3>}
        open={isModalVisible}
        onOk={handleOk}
        onCancel={() => setIsModalVisible(false)}
        confirmLoading={submitting}
        width={700}
        footer={[
          <Button key="submit" type="primary" onClick={handleOk} loading={submitting} className="rounded-xl h-10 px-8 bg-primary font-bold">
            {editingAsset ? 'Lưu Thay Đổi' : 'Tạo Mới'}
          </Button>
        ]}
        className="rounded-[24px] overflow-hidden fancy-modal"
      >
        <Form form={form} layout="vertical" className="mt-4 px-2" validateTrigger="onBlur">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4">
            <Form.Item name="name" label={<span className="font-bold">Tên tài sản</span>} rules={[{ required: true, message: 'Bắt buộc nhập' }]}>
              <Input className="rounded-lg h-10" />
            </Form.Item>
            <Form.Item name="categoryId" label={<span className="font-bold">Danh mục</span>}>
              <Select className="rounded-lg h-10" allowClear>
                {categories.filter(c => c.isActive).map(c => <Option key={c.id} value={c.id}>{c.name}</Option>)}
              </Select>
            </Form.Item>
            <Form.Item name="hierarchyTemplateId" label={<span className="font-bold">Cấu trúc mẫu (Hierarchy)</span>}>
              <Select className="rounded-lg h-10" allowClear placeholder="Chọn cấu trúc kỹ thuật">
                {templates.filter(t => t.isActive).map(t => <Option key={t.id} value={t.id}>{t.name} ({t.path})</Option>)}
              </Select>
            </Form.Item>
            <Form.Item name="serialNumber" label={<span className="font-bold">Số Serial</span>}>
              <Input className="rounded-lg h-10" />
            </Form.Item>
            <Form.Item name="model" label={<span className="font-bold">Model</span>}>
              <Input className="rounded-lg h-10" />
            </Form.Item>
            <Form.Item name="manufacturer" label={<span className="font-bold">Nhà sản xuất</span>}>
              <Input className="rounded-lg h-10" />
            </Form.Item>
            <Form.Item name="purchaseDate" label={<span className="font-bold">Ngày mua</span>}>
              <DatePicker className="w-full rounded-lg h-10" />
            </Form.Item>
            <Form.Item name="value" label={<span className="font-bold">Giá trị mua</span>}>
              <InputNumber className="w-full rounded-lg h-10" formatter={(v: any) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + ' ₫'} parser={(v: any) => v?.replace(/\$\s?|(,*)|(\s?₫)/g, '') as any} />
            </Form.Item>
            <Form.Item name="status" label={<span className="font-bold">Trạng thái</span>} initialValue="OPERATIONAL">
              <Select className="rounded-lg h-10">
                <Option value="OPERATIONAL">Đang hoạt động</Option>
                <Option value="MAINTENANCE">Bảo trì</Option>
                <Option value="BROKEN">Hỏng hóc</Option>
                <Option value="DECOMMISSIONED">Thanh lý</Option>
                <Option value="RESERVED">Dự trữ</Option>
              </Select>
            </Form.Item>
            <Form.Item name="locationId" label={<span className="font-bold">Vị trí</span>} className="md:col-span-2">
              <Select className="rounded-lg h-10" allowClear placeholder="Chọn vị trí">
                {locations.filter(l => l.isActive).map(l => <Option key={l.id} value={l.id}>{l.name}</Option>)}
              </Select>
            </Form.Item>
          </div>
        </Form>
      </Modal>

      <Modal
        title={<h3 className="text-xl font-black text-neutral-900 m-0 pb-3 border-b border-neutral-100">Di Chuyển Tài Sản</h3>}
        open={isMoveModalVisible}
        onOk={handleMoveOk}
        onCancel={() => { setIsMoveModalVisible(false); setMovingLocationId(undefined); }}
        confirmLoading={movingSubmitting}
        width={500}
        footer={[
          <Button key="submit" type="primary" onClick={handleMoveOk} loading={movingSubmitting} className="rounded-xl h-10 px-8 bg-primary font-bold">
            Xác Nhận Di Chuyển
          </Button>
        ]}
        className="rounded-[24px] overflow-hidden fancy-modal"
      >
        <div className="mt-4 px-2 pb-4">
          <p className="text-sm text-neutral-600 mb-4">Chọn vị trí mới cho tài sản <strong className="text-neutral-900">{selectedAsset?.name}</strong>.</p>
          <div className="mb-2 font-bold text-neutral-900">Vị trí đích</div>
          <TreeSelect
            showSearch
            style={{ width: '100%' }}
            value={movingLocationId}
            styles={{ popup: { root: { maxHeight: 400, overflow: 'auto' } } }}
            placeholder="Chọn vị trí..."
            allowClear
            treeDefaultExpandAll
            onChange={(val) => setMovingLocationId(val as string)}
            treeData={locationTreeData}
            treeNodeFilterProp="title"
            className="h-10 rounded-lg custom-tree-select"
          />
        </div>
      </Modal>

      {/* Print Filter Modal */}
      <Modal
        title="Bộ lọc In / Xuất Tài Sản"
        open={isBulkFilterVisible}
        onCancel={() => setIsBulkFilterVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setIsBulkFilterVisible(false)}>Hủy</Button>,
          <Button key="export" icon={<i className="ph ph-file-xls"></i>} onClick={executeExportData}>Xuất Excel</Button>,
          <Button key="print" type="primary" icon={<i className="ph ph-printer"></i>} onClick={executePrintAllQR}>In Mã QR</Button>
        ]}
      >
        <div className="space-y-4 pt-4">
          <div>
            <div className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Trạng thái</div>
            <Select className="w-full" allowClear placeholder="Tất cả trạng thái" value={bulkStatusFilter} onChange={setBulkStatusFilter}>
              <Option value="OPERATIONAL">Đang hoạt động</Option>
              <Option value="MAINTENANCE">Bảo trì</Option>
              <Option value="BROKEN">Hỏng hóc</Option>
              <Option value="DECOMMISSIONED">Thanh lý</Option>
              <Option value="RESERVED">Dự trữ</Option>
            </Select>
          </div>
          <div>
            <div className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Danh mục</div>
            <Select className="w-full" allowClear placeholder="Tất cả danh mục" value={bulkCategoryFilter} onChange={setBulkCategoryFilter}>
              {categories.filter(c => c.isActive).map(c => <Option key={c.id} value={c.id}>{c.name}</Option>)}
            </Select>
          </div>
          <div>
            <div className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Vị trí</div>
            <TreeSelect
              className="w-full"
              allowClear
              placeholder="Tất cả vị trí"
              treeData={locationTreeData}
              value={bulkLocationFilter}
              onChange={setBulkLocationFilter}
              treeDefaultExpandAll
            />
          </div>
          <div>
            <div className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Mẫu phân cấp</div>
            <Select className="w-full" allowClear placeholder="Tất cả mẫu" value={bulkTemplateFilter} onChange={setBulkTemplateFilter}>
              {templates.filter(t => t.isActive).map(t => <Option key={t.id} value={t.id}>{t.name}</Option>)}
            </Select>
          </div>
        </div>
      </Modal>

      {/* Import Assets Modal */}
      <Modal
        title={null}
        open={isImportVisible}
        onCancel={() => setIsImportVisible(false)}
        footer={null}
        className="rounded-3xl overflow-hidden p-0 fancy-modal"
        width={560}
        closeIcon={
          <div className="w-8 h-8 rounded-full bg-white/20 backdrop-blur-md border border-white/30 flex items-center justify-center text-white hover:bg-danger hover:border-danger transition-all z-50">
            <i className="ph ph-x text-base"></i>
          </div>
        }
        styles={{ body: { padding: 0 } }}
      >
        <div className="relative overflow-hidden bg-white flex flex-col">
          <div className="relative p-6 pb-10 bg-gradient-to-br from-primary-600 to-info overflow-hidden shrink-0">
            <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl -mr-16 -mt-16 pointer-events-none"></div>

            <div className="relative z-10 flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-white shadow-lg transform -rotate-3 hover:rotate-0 hover:scale-105 transition-all duration-300">
                <i className="ph-fill ph-file-xls text-3xl drop-shadow-sm"></i>
              </div>
              <div>
                <h3 className="text-2xl font-black text-white m-0 tracking-tight drop-shadow-sm">Bulk Import Assets</h3>
                <p className="text-primary-100 font-medium m-0 mt-1 text-[13px] opacity-90">Onboard multiple assets via spreadsheet</p>
              </div>
            </div>
          </div>

          <div className="p-6 -mt-6 bg-white rounded-t-3xl relative z-20 shadow-[0_-10px_20px_rgba(0,0,0,0.05)] flex-1">
            <div className="mb-5 p-3.5 bg-info/5 rounded-xl border border-info/20 flex items-start gap-3">
              <i className="ph-fill ph-info text-info text-xl mt-0.5 shrink-0"></i>
              <div>
                <p className="text-[13px] font-bold text-neutral-800 m-0 mb-1 flex items-center gap-2">
                  Format: <span className="font-mono text-[11px] bg-white px-1.5 py-0.5 rounded border border-neutral-200 text-info font-bold tracking-wide">Name, Category, Template, Serial...</span>
                </p>
                <p className="text-[12px] text-neutral-500 m-0 leading-relaxed font-medium">
                  First row is header. <a onClick={downloadTemplate} className="text-primary hover:underline cursor-pointer">Download template</a> to see the required structure.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border-2 border-dashed border-primary/30 hover:border-primary bg-neutral-50/50 hover:bg-primary/5 transition-all duration-300 overflow-hidden group">
              <Upload.Dragger
                name="file"
                accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="overflow-hidden"
                style={{ border: 'none', background: 'transparent' }}
                showUploadList={false}
                customRequest={async ({ file, onSuccess, onError }: any) => {
                  try {
                    let uploadFile = file;
                    const isExcel = file.name.endsWith('.xlsx') || file.type.includes('spreadsheetml');

                    if (isExcel) {
                      const buffer = await file.arrayBuffer();
                      const workbook = XLSX.read(buffer, { type: 'array' });
                      const firstSheetName = workbook.SheetNames[0];
                      const worksheet = workbook.Sheets[firstSheetName];
                      const csvData = XLSX.utils.sheet_to_csv(worksheet);
                      uploadFile = new File([new Uint8Array([0xEF, 0xBB, 0xBF]), csvData], file.name.replace('.xlsx', '.csv'), { type: 'text/csv;charset=utf-8' });
                    }

                    const res = await importAssets(uploadFile);
                    const data = res.data;

                    if (data.failureCount > 0) {
                      Modal.error({
                        title: 'Import Errors Detected',
                        width: 600,
                        content: (
                          <div className="mt-4">
                            <p className="mb-3 text-neutral-600 font-medium text-[14px]">
                              Please fix the following issues in your file:
                            </p>
                            <div className="max-h-72 overflow-y-auto text-[13px] text-danger bg-danger/5 border border-danger/20 p-3 rounded-xl font-mono">
                              {data.errors.map((e: string, i: number) => (
                                <div key={i} className="mb-2 pb-2 border-b border-danger/10 last:border-0 last:mb-0 last:pb-0 flex items-start gap-2">
                                  <i className="ph-fill ph-warning-circle mt-0.5 shrink-0"></i>
                                  <span>{e}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        ),
                        okButtonProps: { className: 'rounded-xl h-10 px-6 font-bold' }
                      });
                    } else {
                      message.success(`Đã nhập thành công ${data.successCount} tài sản.`);
                      setIsImportVisible(false);
                    }

                    onSuccess();
                    fetchAssetTree(debouncedSearch, statusFilter || '', categoryFilter || '');
                  } catch (err) {
                    message.error('File import failed. Please check format.');
                    onError(err);
                  }
                }}
              >
                <div className="py-10 px-6 flex flex-col items-center justify-center relative">
                  <div className="w-20 h-20 mb-4 relative flex items-center justify-center transform group-hover:-translate-y-1 transition-transform duration-300">
                    <div className="absolute inset-0 bg-primary/20 rounded-full blur-xl group-hover:bg-primary/30 transition-colors"></div>
                    <div className="w-16 h-16 bg-white rounded-2xl shadow-[0_8px_20px_rgba(0,160,226,0.12)] border border-primary/10 flex items-center justify-center text-primary relative z-10 rotate-3 group-hover:rotate-6 transition-transform duration-300">
                      <UploadOutlined className="text-3xl drop-shadow-sm" />
                    </div>
                  </div>
                  <h4 className="text-lg font-black text-neutral-800 m-0 mb-1 relative z-10">Select or drop file</h4>
                  <p className="text-neutral-500 font-medium text-[13px] text-center max-w-[250px] relative z-10">
                    Upload <span className="font-bold text-info">.CSV</span> or <span className="font-bold text-success">.XLSX</span> files.
                  </p>
                </div>
              </Upload.Dragger>
            </div>
          </div>
        </div>
      </Modal>

      {/* Hidden Printable QR Grid for Bulk Print */}
      {isPrintingAll && createPortal(
        <div className="print-only">
          <div className="grid grid-cols-3 gap-8 p-8" style={{ width: '100%', boxSizing: 'border-box' }}>
            {assetsToPrint.map(asset => (
              <div key={asset.id} className="border border-neutral-800 p-6 flex flex-col items-center justify-center text-center bg-white" style={{ breakInside: 'avoid', minWidth: '200px' }}>
                <QRCodeCanvas value={asset.qrCode} size={150} level="H" />
                <p className="mt-4 font-bold text-[16px] text-black leading-snug m-0">{asset.name}</p>
                <p className="text-[14px] text-black font-mono mt-2 font-bold m-0">{asset.qrCode}</p>
                <p className="text-[12px] text-neutral-600 mt-2 uppercase tracking-wider m-0">{asset.categoryName || 'N/A'}</p>
              </div>
            ))}
          </div>
        </div>,
        document.body
      )}

      <CreateWorkOrderDrawer
        visible={isWorkOrderModalVisible}
        onClose={() => setIsWorkOrderModalVisible(false)}
        initialAssetId={selectedAsset?.id}
      />
    </div>
  );
};
