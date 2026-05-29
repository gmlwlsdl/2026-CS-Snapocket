'use client'

import { useCallback, useState } from 'react'
import { Modal, Button, Group, Text, Stack } from '@mantine/core'
import { Dropzone, type FileWithPath, MIME_TYPES } from '@mantine/dropzone'
import { t as translate } from '@/shared/lib/i18n'
import { useToast } from '@/shared/ui'

import { UploadSimpleIcon, XIcon } from '@phosphor-icons/react'

const ACCEPTED_MIME: string[] = [
  MIME_TYPES.pdf,
  MIME_TYPES.jpeg,
  MIME_TYPES.png,
  'video/mp4',
]

interface UploadModalProps {
  open: boolean
  onClose: () => void
  onUpload: (file: File) => void
}

export function UploadModal({ open, onClose, onUpload }: UploadModalProps) {
  const [selectedFile, setSelectedFile] = useState<FileWithPath | null>(null)
  const { toast } = useToast()

  const handleDrop = useCallback((files: FileWithPath[]) => {
    if (files[0]) setSelectedFile(files[0])
  }, [])

  const handleReject = useCallback(() => {
    toast.error(translate('invalidUploadFileType', 'ko'))
  }, [toast])

  const handleStartAnalysis = useCallback(() => {
    if (!selectedFile) return

    onUpload(selectedFile)
    setSelectedFile(null)
    onClose()
  }, [selectedFile, onUpload, onClose])

  const handleClose = useCallback(() => {
    setSelectedFile(null)
    onClose()
  }, [onClose])

  return (
    <Modal
      opened={open}
      onClose={handleClose}
      title={
        <div>
          <Text fw={800} size="xl" ff="var(--font-manrope), Manrope, sans-serif" style={{ letterSpacing: '-0.6px' }}>
            {translate('uploadSources', 'ko')}
          </Text>
          <Text size="sm" c="dimmed" mt={2}>
            {translate('feedYourKnowledgeVault', 'ko')}
          </Text>
        </div>
      }
      size={672}
      padding="xl"
      styles={{
        header: { paddingBottom: 0 },
        body: { paddingTop: 16 },
      }}
    >
      <Stack gap="lg">
        <Dropzone
          onDrop={handleDrop}
          onReject={handleReject}
          accept={ACCEPTED_MIME}
          maxFiles={1}
          styles={{
            root: {
              minHeight: 280,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px dashed var(--mantine-color-default-border)',
              // background: 'var(--mantine-color-default)',
              borderRadius: 'var(--mantine-radius-md)',
            },
          }}
        >
          <Stack align="center" gap="md" style={{ pointerEvents: 'none' }}>
            <Dropzone.Accept>
              <div
                style={{
                  width: 80,
                  height: 80,
                  borderRadius: '50%',
                  background: 'rgba(151,194,236,0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <UploadSimpleIcon size={20} weight="fill" />
              </div>
            </Dropzone.Accept>
            <Dropzone.Reject>
              <div
                style={{
                  width: 80,
                  height: 80,
                  borderRadius: '50%',
                  background: 'rgba(239,68,68,0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <XIcon size={20} />
              </div>
            </Dropzone.Reject>
            <Dropzone.Idle>
              <div
                style={{
                  width: 80,
                  height: 80,
                  borderRadius: '50%',
                  background: 'rgba(151,194,236,0.1)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <UploadSimpleIcon size={20} weight="fill" />
              </div>
            </Dropzone.Idle>

            <div style={{ textAlign: 'center' }}>
              <Text fw={600} size="lg" ff="var(--font-manrope), Manrope, sans-serif">
                {selectedFile ? selectedFile.name : translate('dropFilesHereOrClickToBrowse', 'ko')}
              </Text>
              <Text size="xs" c="dimmed" mt={4} style={{ letterSpacing: '0.08em' }}>
                {translate('supportForPdfJpgPngOrMp4', 'ko')}
              </Text>
            </div>

            <Button
              variant='transparent'
              radius="xl"
              px="xl"
              disabled={Boolean(selectedFile)}
              onClick={(e) => e.stopPropagation()}
            >
              {translate('selectFiles', 'ko')}
            </Button>
          </Stack>
        </Dropzone>

        <Group justify="flex-end" gap="sm">
          <Button variant="subtle" color="gray" radius="xl" onClick={handleClose}>
            {translate('cancel', 'ko')}
          </Button>
          <Button
            radius="xl"
            px="xl"
            disabled={!selectedFile}
            onClick={handleStartAnalysis}
            style={{
              background: selectedFile
                ? 'linear-gradient(90deg, #97c2ec 0%, #7daed8 100%)'
                : 'var(--mantine-color-gray-2)',
              color: selectedFile ? '#0d2b45' : 'var(--mantine-color-gray-5)',
              fontWeight: 700,
            }}
          >
            {translate('startAnalysis', 'ko')}
          </Button>
        </Group>
      </Stack>
    </Modal>
  )
}
