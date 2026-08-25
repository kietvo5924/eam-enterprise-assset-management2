package com.eam.api.core.tenant;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;
import java.util.UUID;

@Converter
public class StringToUuidConverter implements AttributeConverter<String, UUID> {

    @Override
    public UUID convertToDatabaseColumn(String attribute) {
        if (attribute == null || attribute.isEmpty()) {
            return null;
        }
        return UUID.fromString(attribute);
    }

    @Override
    public String convertToEntityAttribute(UUID dbData) {
        if (dbData == null) {
            return null;
        }
        return dbData.toString();
    }
}
