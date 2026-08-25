package com.eam.api.models.dtos.tree;

import com.eam.api.models.dtos.AssetResponse;
import java.util.List;
import java.util.UUID;

public record LocationTreeNode(
        UUID id,
        String name,
        String parentId,
        Boolean isActive,
        List<AssetResponse> assets,
        List<LocationTreeNode> children
) {}
