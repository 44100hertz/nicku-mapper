local cairo = require "oocairo"
local styles = require "styles"

local function render_to_svg (entity_list, outfile)
   -- Calculate dimensions
   local min_x, min_z, max_x, max_z = 0,0,0,0
   local points = {}
   for _,entity in ipairs(entity_list) do
      min_x = math.min(entity.x - (entity.w and entity.w/2 or 0), min_x)
      min_z = math.min(entity.z - (entity.d and entity.d/2 or 0), min_z)
      max_x = math.max(entity.x + (entity.w and entity.w/2 or 0), max_x)
      max_z = math.max(entity.z + (entity.d and entity.d/2 or 0), max_z)
   end
   do
      local pad = 5
      min_x = min_x - pad
      max_x = max_x + pad
      min_z = min_z - pad
      max_z = max_z + pad
   end

   local scale = 10
   local surface = cairo.svg_surface_create(
      outfile, (max_x-min_x)*scale, (max_z-min_z)*scale
   )
   local cr = cairo.context_create(surface)
   cr:set_source_rgb(1.0, 1.0, 1.0, 1.0)
   cr:rectangle()
   cr:fill()
   cr:set_line_width(0.25)
   cr:scale(scale, scale)
   cr:translate(-min_x, -min_z)

   local function draw_line_to_actor_named(name)
      for _,obj in ipairs(entity_list) do
         if obj.name == name then
            cr:line_to(obj.x, obj.z)
            cr:stroke()
            return
         end
      end
      io.write('Warning: could not find actor with name: ' .. name .. ' for ' .. outfile .. '\n')
   end

   -- Draw connections (bottom layer)
   for _,entity in ipairs(entity_list) do
      if entity.target then
         cr:set_source_rgb(1,0.8,0.5)
         for i,targ in ipairs(entity.target) do
            cr:move_to(entity.x, entity.z)
            draw_line_to_actor_named(targ)
         end
      end

      if entity.parent then
         cr:set_source_rgb(0.8,0.8,0.8)
         cr:move_to(entity.x, entity.z)
         draw_line_to_actor_named(entity.parent)
      end

      if entity.next_waypoint then
         cr:set_source_rgb(0.0,0.5,0.0)
         cr:move_to(entity.x, entity.z)
         draw_line_to_actor_named(entity.next_waypoint)
      end

      if entity.respawn_point then
         cr:set_source_rgb(0.5,0.5,0.3)
         cr:move_to(entity.x, entity.z)
         cr:line_to(entity.respawn_point.x, entity.respawn_point.z)
         cr:stroke()
      end

      if entity.respawn_points then
         cr:set_source_rgb(0.5,0.5,0.5)
         for i,respawn in ipairs(entity.respawn_points) do
            cr:move_to(entity.x, entity.z)
            draw_line_to_actor_named(respawn)
         end
      end
   end

   -- Draw bounding boxes and connections (middle layer)
   for _,entity in ipairs(entity_list) do
      local style = styles[entity.type] or styles.default
      style.size = style.size or styles.default.size

      if entity.path then
         cr:set_source_rgb(0,0,0)
         cr:move_to(entity.path[1], entity.path[3])
         for i=8, #entity.path, 7 do
            if not entity.path[i+2] then break end
            cr:line_to(entity.path[i], entity.path[i+2])
         end
         cr:stroke()
      end

      cr:set_source_rgb(table.unpack(style.col))

      if entity.w and entity.d then
         cr:move_to(entity.x, entity.z)
         cr:rectangle(entity.x-entity.w/2, entity.z-entity.d/2, entity.w, entity.d)
         cr:stroke()
      else
         cr:move_to(entity.x + style.size, entity.z)
         cr:arc(entity.x, entity.z, style.size, 0, 2*math.pi)
         cr:stroke()
      end
   end

   -- Draw descriptions (top layer)
   for _,entity in ipairs(entity_list) do
      local style = styles[entity.type] or styles.default
      if style.describe then
         local str = entity[style.describe]
         if not str:match('NToons Entity Instance%d+') then
            cr:set_font_size(1)
            local dim = cr:text_extents(str)
            cr:set_source_rgb(0,0,0)
            cr:move_to(entity.x - dim.width / 2, entity.z - dim.height / 2)
            cr:text_path(str)
            cr:stroke_preserve()
            cr:set_source_rgb(1,1,1)
            cr:fill()
         end
      end

   end

   surface:finish()
end

return render_to_svg
