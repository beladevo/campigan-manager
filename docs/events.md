# Event Payloads

## campaign.video.requested
```json
{
  "userId": "u123",
  "campaignId": "cmp456",
  "prompt": "Create a video for my new blender"
}
```

## campaign.video.completed
```json
{
  "campaignId": "cmp456",
  "status": "completed",
  "videoUrl": "http://videos.example.com/cmp456.mp4",
  "error": null,
  "duration": "14s"
}
```
