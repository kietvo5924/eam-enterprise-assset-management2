package com.eam.api.models.dtos.tree;

import com.eam.api.models.dtos.AssetResponse;
import java.util.List;

public record AssetTreeResponse(
        List<LocationTreeNode> locations,
        List<AssetResponse> unassignedAssets
) {}
